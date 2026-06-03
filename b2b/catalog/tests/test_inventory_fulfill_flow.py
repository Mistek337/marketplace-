"""OpenAPI POST /api/v1/inventory/fulfill — fulfill-delivery flow (US-B2B-10)."""

import uuid

from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from catalog.models import Category, Product, SKU


@override_settings(B2C_TO_B2B_KEY="test-b2c-key")
class InventoryFulfillFlowTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.headers = {"HTTP_X_SERVICE_KEY": "test-b2c-key"}
        self.reserve_url = "/api/v1/inventory/reserve"
        self.fulfill_url = "/api/v1/inventory/fulfill"
        self.category = Category.objects.create(name="Phones")
        self.product = Product.objects.create(
            title="Phone",
            description="d",
            category=self.category,
            seller_id=uuid.uuid4(),
            status=Product.Status.MODERATED,
        )
        self.sku = SKU.objects.create(
            product=self.product,
            name="128GB",
            price=100_000,
            active_quantity=10,
            reserved_quantity=0,
        )

    def _reserve(self, *, order_id=None, quantity=4):
        order_id = order_id or uuid.uuid4()
        payload = {
            "idempotency_key": str(uuid.uuid4()),
            "order_id": str(order_id),
            "items": [{"sku_id": str(self.sku.id), "quantity": quantity}],
        }
        resp = self.client.post(self.reserve_url, payload, format="json", **self.headers)
        self.assertEqual(resp.status_code, 200)
        return order_id, quantity

    def _fulfill_payload(self, order_id, quantity):
        return {
            "order_id": str(order_id),
            "items": [{"sku_id": str(self.sku.id), "quantity": quantity}],
        }

    def test_fulfill_decreases_reserved_quantity(self):
        order_id, quantity = self._reserve(quantity=4)
        self.sku.refresh_from_db()
        self.assertEqual(self.sku.reserved_quantity, 4)

        resp = self.client.post(
            self.fulfill_url,
            self._fulfill_payload(order_id, quantity),
            format="json",
            **self.headers,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["status"], "FULFILLED")
        self.assertEqual(resp.json()["order_id"], str(order_id))

        self.sku.refresh_from_db()
        self.assertEqual(self.sku.reserved_quantity, 0)

    def test_active_quantity_unchanged(self):
        order_id, quantity = self._reserve(quantity=3)
        self.sku.refresh_from_db()
        active_before = self.sku.active_quantity
        self.assertEqual(active_before, 7)

        resp = self.client.post(
            self.fulfill_url,
            self._fulfill_payload(order_id, quantity),
            format="json",
            **self.headers,
        )
        self.assertEqual(resp.status_code, 200)

        self.sku.refresh_from_db()
        self.assertEqual(self.sku.active_quantity, active_before)
        self.assertEqual(self.sku.reserved_quantity, 0)
        self.assertEqual(self.sku.stock_quantity, active_before)

    def test_idempotent_fulfill_no_double_deduction(self):
        order_id, quantity = self._reserve(quantity=2)

        payload = self._fulfill_payload(order_id, quantity)
        first = self.client.post(self.fulfill_url, payload, format="json", **self.headers)
        second = self.client.post(self.fulfill_url, payload, format="json", **self.headers)
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(first.json(), second.json())

        self.sku.refresh_from_db()
        self.assertEqual(self.sku.reserved_quantity, 0)
        self.assertEqual(self.sku.active_quantity, 8)

    def test_missing_service_key_returns_401(self):
        order_id, quantity = self._reserve()
        resp = self.client.post(
            self.fulfill_url,
            self._fulfill_payload(order_id, quantity),
            format="json",
        )
        self.assertEqual(resp.status_code, 401)
