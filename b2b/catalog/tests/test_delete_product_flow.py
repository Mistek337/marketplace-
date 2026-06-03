"""OpenAPI DELETE /api/v1/products/{product_id} — delete-product flow."""

import uuid
from unittest.mock import patch

from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from catalog.models import B2COutboxEvent, ModerationOutboxEvent, Product, SKU
from catalog.models import Category
from sellers.models import Seller


class DeleteProductFlowTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.seller = Seller.objects.create(
            email="seller-del@example.com",
            password="hashed",
            first_name="Del",
            last_name="Seller",
            company_name="Del Ltd",
        )
        self.other = Seller.objects.create(
            email="other-del@example.com",
            password="hashed",
            first_name="Other",
            last_name="User",
            company_name="Other Ltd",
        )
        self.category = Category.objects.create(name="Gadgets")
        self.product = Product.objects.create(
            title="Widget",
            description="Desc",
            category=self.category,
            status=Product.Status.MODERATED,
            seller_id=self.seller.id,
            slug="widget",
            deleted=False,
        )
        self.sku1 = SKU.objects.create(
            product=self.product,
            name="Red",
            price=10_000,
            active_quantity=3,
        )
        self.sku2 = SKU.objects.create(
            product=self.product,
            name="Blue",
            price=12_000,
            active_quantity=1,
        )
        self.client.force_authenticate(user=self.seller)

    @patch("catalog.b2c_client._deliver_b2c_b2b_events", return_value=True)
    @patch("catalog.moderation_client._deliver_moderation_b2b_events", return_value=True)
    def test_delete_sets_deleted_true(self, _mod_deliver, _b2c_deliver):
        resp = self.client.delete(f"/api/v1/products/{self.product.id}")
        self.assertEqual(resp.status_code, 204)

        self.product.refresh_from_db()
        self.assertTrue(self.product.deleted)

    @patch("catalog.b2c_client._deliver_b2c_b2b_events", return_value=True)
    @patch("catalog.moderation_client._deliver_moderation_b2b_events")
    def test_delete_emits_event_to_moderation(self, mod_deliver, _b2c_deliver):
        mod_deliver.return_value = True

        self.client.delete(f"/api/v1/products/{self.product.id}")

        outbox = ModerationOutboxEvent.objects.get(product_id=self.product.id)
        self.assertEqual(outbox.event, "DELETED")
        self.assertEqual(outbox.payload["event_type"], "PRODUCT_DELETED")
        self.assertEqual(
            outbox.payload["payload"]["product_id"],
            str(self.product.id),
        )
        mod_deliver.assert_called_once()

    @patch("catalog.moderation_client._deliver_moderation_b2b_events", return_value=True)
    @patch("catalog.b2c_client._deliver_b2c_b2b_events")
    def test_delete_emits_product_deleted_to_b2c(self, b2c_deliver, _mod_deliver):
        b2c_deliver.return_value = True

        self.client.delete(f"/api/v1/products/{self.product.id}")

        outbox = B2COutboxEvent.objects.get(event="PRODUCT_DELETED")
        self.assertEqual(str(outbox.product_id), str(self.product.id))
        payload = outbox.payload
        self.assertEqual(payload["event_type"], "PRODUCT_DELETED")
        sku_ids = set(payload["payload"]["sku_ids"])
        self.assertEqual(sku_ids, {str(self.sku1.id), str(self.sku2.id)})
        b2c_deliver.assert_called_once()

    def test_delete_already_deleted_returns_404(self):
        self.product.deleted = True
        self.product.save(update_fields=["deleted"])

        resp = self.client.delete(f"/api/v1/products/{self.product.id}")
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(resp.json()["code"], "NOT_FOUND")

    def test_delete_nonexistent_returns_404(self):
        resp = self.client.delete(f"/api/v1/products/{uuid.uuid4()}")
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(resp.json()["code"], "NOT_FOUND")

    def test_delete_unauthenticated_returns_401(self):
        self.client.force_authenticate(user=None)
        resp = self.client.delete(f"/api/v1/products/{self.product.id}")
        self.assertEqual(resp.status_code, 401)
        self.assertEqual(resp.json()["code"], "UNAUTHORIZED")

    def test_delete_others_product_returns_403(self):
        self.client.force_authenticate(user=self.other)

        resp = self.client.delete(f"/api/v1/products/{self.product.id}")
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(resp.json()["code"], "NOT_OWNER")

        self.product.refresh_from_db()
        self.assertFalse(self.product.deleted)

    def test_deleted_product_not_in_seller_list(self):
        self.product.deleted = True
        self.product.save(update_fields=["deleted"])

        resp = self.client.get("/api/v1/products")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertIn("total_count", body)
        self.assertIn("items", body)
        ids = {item["id"] for item in body["items"]}
        self.assertNotIn(str(self.product.id), ids)
