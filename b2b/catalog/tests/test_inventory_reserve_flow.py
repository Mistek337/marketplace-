import json
import uuid
from unittest.mock import patch

from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from catalog.api_errors import CONFLICT, NOT_FOUND
from catalog.models import B2COutboxEvent, Category, InventoryReservation, Product, SKU


@override_settings(B2C_TO_B2B_KEY="test-b2c-key")
class InventoryReserveFlowTests(TestCase):
    """Канон reserve-sku: /api/v1/inventory/reserve и /unreserve."""

    def setUp(self):
        self.client = APIClient()
        self.headers = {"HTTP_X_SERVICE_KEY": "test-b2c-key"}
        self.reserve_url = "/api/v1/inventory/reserve/"
        self.unreserve_url = "/api/v1/inventory/unreserve/"
        self.category = Category.objects.create(name="Phones")
        self.product = Product.objects.create(
            title="iPhone",
            description="d",
            category=self.category,
            seller_id=uuid.uuid4(),
            status=Product.Status.MODERATED,
        )

    def _sku(self, *, active: int, reserved: int = 0, name: str = "128GB") -> SKU:
        return SKU.objects.create(
            product=self.product,
            name=name,
            price=100_000,
            active_quantity=active,
            reserved_quantity=reserved,
        )

    def _reserve_payload(
        self,
        *,
        order_id=None,
        idempotency_key=None,
        items,
    ):
        return {
            "idempotency_key": str(idempotency_key or uuid.uuid4()),
            "order_id": str(order_id or uuid.uuid4()),
            "items": items,
        }

    def test_reserve_all_skus_succeeds(self):
        sku_a = self._sku(active=10, name="A")
        sku_b = self._sku(active=5, name="B")
        order_id = uuid.uuid4()
        payload = self._reserve_payload(
            order_id=order_id,
            items=[
                {"sku_id": str(sku_a.id), "quantity": 3},
                {"sku_id": str(sku_b.id), "quantity": 2},
            ],
        )

        resp = self.client.post(self.reserve_url, payload, format="json", **self.headers)
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["order_id"], str(order_id))
        self.assertEqual(body["status"], "RESERVED")
        self.assertTrue(body["reserved_at"].endswith("Z"))

        sku_a.refresh_from_db()
        sku_b.refresh_from_db()
        self.assertEqual(sku_a.active_quantity, 7)
        self.assertEqual(sku_a.reserved_quantity, 3)
        self.assertEqual(sku_b.active_quantity, 3)
        self.assertEqual(sku_b.reserved_quantity, 2)
        self.assertEqual(sku_a.stock_quantity, 10)
        self.assertEqual(sku_b.stock_quantity, 5)

    def test_partial_insufficient_stock_returns_409_all_rollback(self):
        sku_ok = self._sku(active=10, name="OK")
        sku_low = self._sku(active=1, name="LOW")
        before_ok = (sku_ok.active_quantity, sku_ok.reserved_quantity)
        before_low = (sku_low.active_quantity, sku_low.reserved_quantity)

        payload = self._reserve_payload(
            items=[
                {"sku_id": str(sku_ok.id), "quantity": 2},
                {"sku_id": str(sku_low.id), "quantity": 5},
            ],
        )
        resp = self.client.post(self.reserve_url, payload, format="json", **self.headers)

        self.assertEqual(resp.status_code, 409)
        self.assertEqual(resp.json()["code"], CONFLICT)
        self.assertIn("skus", resp.json()["details"])
        problem_ids = {row["sku_id"] for row in resp.json()["details"]["skus"]}
        self.assertIn(str(sku_low.id), problem_ids)

        sku_ok.refresh_from_db()
        sku_low.refresh_from_db()
        self.assertEqual((sku_ok.active_quantity, sku_ok.reserved_quantity), before_ok)
        self.assertEqual((sku_low.active_quantity, sku_low.reserved_quantity), before_low)
        self.assertFalse(InventoryReservation.objects.exists())

    def test_idempotent_reserve_returns_200_without_double_deduction(self):
        sku = self._sku(active=4)
        order_id = uuid.uuid4()
        idempotency_key = uuid.uuid4()
        payload = self._reserve_payload(
            order_id=order_id,
            idempotency_key=idempotency_key,
            items=[{"sku_id": str(sku.id), "quantity": 2}],
        )

        first = self.client.post(self.reserve_url, payload, format="json", **self.headers)
        second = self.client.post(self.reserve_url, payload, format="json", **self.headers)
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(first.json(), second.json())

        sku.refresh_from_db()
        self.assertEqual(sku.active_quantity, 2)
        self.assertEqual(sku.reserved_quantity, 2)
        self.assertEqual(InventoryReservation.objects.count(), 1)

    @override_settings(
        B2C_EVENTS_BASE_URL="https://b2c.example",
        B2B_TO_B2C_KEY="b2c-events-key",
    )
    @patch("catalog.b2c_client.request.urlopen")
    def test_sku_out_of_stock_event_emitted(self, urlopen_mock):
        sku = self._sku(active=2)
        payload = self._reserve_payload(
            items=[{"sku_id": str(sku.id), "quantity": 2}],
        )

        resp = self.client.post(self.reserve_url, payload, format="json", **self.headers)
        self.assertEqual(resp.status_code, 200)

        sku.refresh_from_db()
        self.assertEqual(sku.active_quantity, 0)

        self.assertEqual(B2COutboxEvent.objects.filter(event="SKU_OUT_OF_STOCK").count(), 1)
        outbox = B2COutboxEvent.objects.get()
        self.assertEqual(str(outbox.sku_id), str(sku.id))
        self.assertEqual(str(outbox.product_id), str(self.product.id))

        self.assertTrue(urlopen_mock.called)
        request_obj = urlopen_mock.call_args.args[0]
        body = json.loads(request_obj.data.decode("utf-8"))
        self.assertEqual(body["event"], "SKU_OUT_OF_STOCK")
        self.assertEqual(body["sku_id"], str(sku.id))

    def test_unreserve_restores_quantities(self):
        sku = self._sku(active=8)
        order_id = uuid.uuid4()
        reserve_payload = self._reserve_payload(
            order_id=order_id,
            items=[{"sku_id": str(sku.id), "quantity": 3}],
        )
        reserve_resp = self.client.post(
            self.reserve_url, reserve_payload, format="json", **self.headers
        )
        self.assertEqual(reserve_resp.status_code, 200)

        sku.refresh_from_db()
        self.assertEqual(sku.active_quantity, 5)
        self.assertEqual(sku.reserved_quantity, 3)

        unreserve_payload = {
            "order_id": str(order_id),
            "items": [{"sku_id": str(sku.id), "quantity": 3}],
        }
        unreserve_resp = self.client.post(
            self.unreserve_url, unreserve_payload, format="json", **self.headers
        )
        self.assertEqual(unreserve_resp.status_code, 200)
        self.assertEqual(unreserve_resp.json()["status"], "UNRESERVED")
        self.assertTrue(unreserve_resp.json()["processed_at"].endswith("Z"))

        sku.refresh_from_db()
        self.assertEqual(sku.active_quantity, 8)
        self.assertEqual(sku.reserved_quantity, 0)

        second = self.client.post(
            self.unreserve_url, unreserve_payload, format="json", **self.headers
        )
        self.assertEqual(second.status_code, 200)

    def test_reserve_missing_service_key_returns_401(self):
        sku = self._sku(active=1)
        payload = self._reserve_payload(items=[{"sku_id": str(sku.id), "quantity": 1}])
        resp = self.client.post(self.reserve_url, payload, format="json")
        self.assertEqual(resp.status_code, 401)

    def test_unreserve_unknown_order_returns_404(self):
        payload = {
            "order_id": str(uuid.uuid4()),
            "items": [{"sku_id": str(uuid.uuid4()), "quantity": 1}],
        }
        resp = self.client.post(self.unreserve_url, payload, format="json", **self.headers)
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(resp.json()["code"], NOT_FOUND)
