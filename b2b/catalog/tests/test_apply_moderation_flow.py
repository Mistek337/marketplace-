import uuid
from datetime import datetime, timezone
from unittest.mock import patch

from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from catalog.models import (
    B2COutboxEvent,
    BlockingReason,
    Category,
    ProcessedModerationEvent,
    Product,
    SKU,
)
from sellers.models import Seller


class ApplyModerationFlowTests(TestCase):
    """OpenAPI POST /api/v1/moderation/events — apply-moderation flow."""

    def setUp(self):
        self.client = APIClient()
        self.moderation_url = "/api/v1/moderation/events"
        self.seller = Seller.objects.create(
            email="seller-mod@example.com",
            password="hashed",
            first_name="Seller",
            last_name="Mod",
            company_name="Mod Ltd",
        )
        self.category = Category.objects.create(name="Electronics")
        self.blocking_reason = BlockingReason.objects.create(
            title="Policy violation",
            comment="Fix listing",
        )
        self.product = Product.objects.create(
            title="Gadget",
            description="Desc",
            category=self.category,
            status=Product.Status.ON_MODERATION,
            seller_id=self.seller.id,
            slug="gadget",
            blocking_reason_id=self.blocking_reason.id,
            moderator_comment="Old comment",
            field_reports=[{"field_name": "title", "sku_id": None, "comment": "bad"}],
        )
        self.sku = SKU.objects.create(
            product=self.product,
            name="Default",
            price=100_00,
            active_quantity=5,
        )
        self.occurred_at = datetime(2026, 5, 31, 12, 0, 0, tzinfo=timezone.utc).isoformat()

    def _headers(self, key="mod-to-b2b-key"):
        return {"HTTP_X_SERVICE_KEY": key}

    def _event_payload(self, **overrides):
        base = {
            "idempotency_key": str(uuid.uuid4()),
            "product_id": str(self.product.id),
            "event_type": "MODERATED",
            "occurred_at": self.occurred_at,
        }
        base.update(overrides)
        return base

    @override_settings(MODERATION_TO_B2B_KEY="mod-to-b2b-key")
    def test_moderated_event_clears_blocking_data(self):
        payload = self._event_payload(event_type="MODERATED")

        resp = self.client.post(
            self.moderation_url,
            payload,
            format="json",
            **self._headers(),
        )
        self.assertEqual(resp.status_code, 204)

        self.product.refresh_from_db()
        self.assertEqual(self.product.status, Product.Status.MODERATED)
        self.assertIsNone(self.product.blocking_reason_id)
        self.assertEqual(self.product.field_reports, [])

    @override_settings(
        MODERATION_TO_B2B_KEY="mod-to-b2b-key",
        B2C_EVENTS_BASE_URL="https://b2c.example",
        B2B_TO_B2C_KEY="b2c-events-key",
    )
    @patch("catalog.b2c_client.request.urlopen")
    def test_blocked_soft_saves_field_reports(self, urlopen_mock):
        reports = [
            {
                "field_name": "description",
                "sku_id": None,
                "comment": "Misleading text",
            }
        ]
        payload = self._event_payload(
            event_type="BLOCKED",
            hard_block=False,
            blocking_reason_id=str(self.blocking_reason.id),
            moderator_comment="Soft block",
            field_reports=reports,
        )

        resp = self.client.post(
            self.moderation_url,
            payload,
            format="json",
            **self._headers(),
        )
        self.assertEqual(resp.status_code, 204)

        self.product.refresh_from_db()
        self.assertEqual(self.product.status, Product.Status.BLOCKED)
        self.assertEqual(self.product.blocking_reason_id, self.blocking_reason.id)
        self.assertEqual(
            self.product.field_reports,
            [
                {
                    "field_name": "description",
                    "sku_id": None,
                    "comment": "Misleading text",
                }
            ],
        )

        outbox = B2COutboxEvent.objects.get(event="PRODUCT_BLOCKED")
        self.assertEqual(str(outbox.product_id), str(self.product.id))
        self.assertIsNone(outbox.sku_id)
        self.assertFalse(outbox.payload["hard_block"])
        self.assertTrue(urlopen_mock.called)

    @override_settings(
        MODERATION_TO_B2B_KEY="mod-to-b2b-key",
        B2C_EVENTS_BASE_URL="https://b2c.example",
        B2B_TO_B2C_KEY="b2c-events-key",
    )
    @patch("catalog.b2c_client.request.urlopen")
    def test_blocked_hard_sets_terminal_status(self, urlopen_mock):
        payload = self._event_payload(
            event_type="BLOCKED",
            hard_block=True,
            blocking_reason_id=str(self.blocking_reason.id),
            field_reports=[],
        )

        resp = self.client.post(
            self.moderation_url,
            payload,
            format="json",
            **self._headers(),
        )
        self.assertEqual(resp.status_code, 204)

        self.product.refresh_from_db()
        self.assertEqual(self.product.status, Product.Status.HARD_BLOCKED)

        body = B2COutboxEvent.objects.get().payload
        self.assertTrue(body["hard_block"])
        self.assertTrue(urlopen_mock.called)

    @override_settings(MODERATION_TO_B2B_KEY="mod-to-b2b-key")
    def test_hard_blocked_product_rejects_seller_edits(self):
        self.product.status = Product.Status.HARD_BLOCKED
        self.product.save(update_fields=["status"])

        self.client.force_authenticate(user=self.seller)
        detail_url = f"/api/v1/products/{self.product.id}"

        patch_resp = self.client.patch(
            detail_url,
            {"title": "New title"},
            format="json",
        )
        self.assertEqual(patch_resp.status_code, 403)

        delete_resp = self.client.delete(detail_url)
        self.assertEqual(delete_resp.status_code, 403)

        self.product.refresh_from_db()
        self.assertEqual(self.product.title, "Gadget")
        self.assertFalse(self.product.deleted)

    @override_settings(MODERATION_TO_B2B_KEY="mod-to-b2b-key")
    def test_duplicate_event_same_idempotency_key_no_side_effects(self):
        key = uuid.uuid4()
        payload = self._event_payload(
            idempotency_key=str(key),
            event_type="MODERATED",
        )

        first = self.client.post(
            self.moderation_url,
            payload,
            format="json",
            **self._headers(),
        )
        self.assertEqual(first.status_code, 204)
        self.product.refresh_from_db()
        first_status = self.product.status
        processed_count = ProcessedModerationEvent.objects.count()
        outbox_count = B2COutboxEvent.objects.count()

        self.product.status = Product.Status.BLOCKED
        self.product.field_reports = [{"field_name": "x", "sku_id": None, "comment": "y"}]
        self.product.save(update_fields=["status", "field_reports"])

        second = self.client.post(
            self.moderation_url,
            payload,
            format="json",
            **self._headers(),
        )
        self.assertEqual(second.status_code, 204)

        self.product.refresh_from_db()
        self.assertEqual(self.product.status, Product.Status.BLOCKED)
        self.assertEqual(ProcessedModerationEvent.objects.count(), processed_count)
        self.assertEqual(B2COutboxEvent.objects.count(), outbox_count)
        self.assertEqual(first_status, Product.Status.MODERATED)

    @override_settings(MODERATION_TO_B2B_KEY="mod-to-b2b-key")
    def test_missing_service_key_returns_401(self):
        payload = self._event_payload(event_type="MODERATED")

        resp = self.client.post(self.moderation_url, payload, format="json")
        self.assertEqual(resp.status_code, 401)

    @override_settings(MODERATION_TO_B2B_KEY="mod-to-b2b-key")
    def test_blocked_without_active_stock_skips_b2c_cascade(self):
        self.sku.active_quantity = 0
        self.sku.save(update_fields=["active_quantity"])

        payload = self._event_payload(
            event_type="BLOCKED",
            hard_block=False,
            blocking_reason_id=str(self.blocking_reason.id),
            field_reports=[],
        )

        resp = self.client.post(
            self.moderation_url,
            payload,
            format="json",
            **self._headers(),
        )
        self.assertEqual(resp.status_code, 204)
        self.assertEqual(B2COutboxEvent.objects.count(), 0)
