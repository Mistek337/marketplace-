"""OpenAPI DELETE /api/v1/skus/{sku_id} — deleteSku (204 / 409)."""

import json
import uuid
from unittest.mock import patch

from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from catalog.api_errors import CONFLICT, FORBIDDEN
from catalog.models import B2COutboxEvent, Category, ModerationOutboxEvent, Product, SKU
from sellers.models import Seller


class DeleteSKUFlowTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.seller = Seller.objects.create(
            email="sku-del@example.com",
            password="hashed",
            first_name="Del",
            last_name="Seller",
            company_name="Del Ltd",
        )
        self.category = Category.objects.create(name="Gadgets")
        self.client.force_authenticate(user=self.seller)

    def _product(self, *, status=Product.Status.MODERATED):
        return Product.objects.create(
            title="Widget",
            description="Desc",
            category=self.category,
            status=status,
            seller_id=self.seller.id,
            slug="widget",
        )

    def _sku(self, product, *, name="Red", active=0, reserved=0):
        return SKU.objects.create(
            product=product,
            name=name,
            price=10_000,
            active_quantity=active,
            reserved_quantity=reserved,
        )

    def test_delete_sku_succeeds(self):
        product = self._product()
        sku = self._sku(product, active=5)
        other = self._sku(product, name="Blue", active=2)

        resp = self.client.delete(f"/api/v1/skus/{sku.id}")
        self.assertEqual(resp.status_code, 204)
        self.assertEqual(resp.content, b"")
        self.assertFalse(SKU.objects.filter(pk=sku.id).exists())
        self.assertTrue(SKU.objects.filter(pk=other.id).exists())

        product.refresh_from_db()
        self.assertEqual(product.status, Product.Status.MODERATED)

    def test_delete_sku_hard_blocked_product_returns_403(self):
        product = self._product(status=Product.Status.HARD_BLOCKED)
        sku = self._sku(product, active=1)

        resp = self.client.delete(f"/api/v1/skus/{sku.id}")
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(resp.json()["code"], FORBIDDEN)
        self.assertEqual(
            resp.json()["message"],
            "Cannot delete SKU of hard-blocked product",
        )
        self.assertTrue(SKU.objects.filter(pk=sku.id).exists())

    def test_delete_sku_with_active_reserves_returns_409(self):
        product = self._product()
        sku = self._sku(product, active=3, reserved=2)

        resp = self.client.delete(f"/api/v1/skus/{sku.id}")
        self.assertEqual(resp.status_code, 409)
        self.assertEqual(resp.json()["code"], CONFLICT)
        self.assertIn("message", resp.json())
        self.assertTrue(SKU.objects.filter(pk=sku.id).exists())

    @patch("catalog.moderation_client._deliver_moderation_b2b_events", return_value=True)
    def test_last_sku_on_moderation_transitions_product_to_created(self, _mod_deliver):
        product = self._product(status=Product.Status.ON_MODERATION)
        sku = self._sku(product, active=1)

        resp = self.client.delete(f"/api/v1/skus/{sku.id}")
        self.assertEqual(resp.status_code, 204)

        product.refresh_from_db()
        self.assertEqual(product.status, Product.Status.CREATED)
        self.assertFalse(SKU.objects.filter(product_id=product.id).exists())

        outbox = ModerationOutboxEvent.objects.get(product_id=product.id)
        self.assertEqual(outbox.event, "DELETED")
        self.assertEqual(outbox.payload["event_type"], "PRODUCT_DELETED")

    @override_settings(
        B2C_EVENTS_BASE_URL="https://b2c.example",
        B2B_TO_B2C_KEY="b2c-events-key",
    )
    @patch("catalog.b2c_client.request.urlopen")
    def test_sku_out_of_stock_event_on_moderated_product(self, urlopen_mock):
        product = self._product(status=Product.Status.MODERATED)
        sku = self._sku(product, active=4, name="Green")
        self._sku(product, name="Blue", active=1)

        resp = self.client.delete(f"/api/v1/skus/{sku.id}")
        self.assertEqual(resp.status_code, 204)

        outbox = B2COutboxEvent.objects.get(event="SKU_OUT_OF_STOCK")
        self.assertEqual(str(outbox.sku_id), str(sku.id))
        self.assertEqual(str(outbox.product_id), str(product.id))

        self.assertTrue(urlopen_mock.called)
        request_obj = urlopen_mock.call_args.args[0]
        body = json.loads(request_obj.data.decode("utf-8"))
        self.assertEqual(body["event"], "SKU_OUT_OF_STOCK")
        self.assertEqual(body["sku_id"], str(sku.id))

    def test_delete_unknown_sku_returns_204(self):
        resp = self.client.delete(f"/api/v1/skus/{uuid.uuid4()}")
        self.assertEqual(resp.status_code, 204)
        self.assertEqual(resp.content, b"")
