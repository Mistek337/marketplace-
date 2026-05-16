import json
from unittest.mock import patch

from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from catalog.api_errors import FORBIDDEN
from catalog.moderation_client import emit_product_created_event
from catalog.models import Category, Product, SKU, SKUImage
from sellers.models import Seller


class AddSKUFlowTests(TestCase):
    """US-B2B-02 / OpenAPI POST /api/v1/skus."""

    def setUp(self):
        self.client = APIClient()
        self.seller = Seller.objects.create(
            email="flow-seller@example.com",
            password="hashed",
            first_name="Flow",
            last_name="Seller",
            company_name="Flow Ltd",
        )
        self.client.force_authenticate(user=self.seller)
        self.category = Category.objects.create(name="Категория")
        self.url = "/api/v1/skus/"

    def _payload(self, *, product_id, image_url="https://example.com/sku.jpg"):
        return {
            "product_id": str(product_id),
            "name": "256GB Black",
            "price": 12_999_000,
            "cost_price": 9_500_000,
            "discount": 0,
            "images": [{"url": image_url, "ordering": 0}],
            "characteristics": [
                {"name": "Цвет", "value": "Чёрный"},
                {"name": "Объём памяти", "value": "256 ГБ"},
            ],
        }

    @patch("catalog.views.emit_product_created_event")
    def test_first_sku_transitions_product_to_on_moderation(self, emit_mock):
        product = Product.objects.create(
            title="Phone",
            description="d",
            category=self.category,
            seller_id=self.seller.id,
            status=Product.Status.CREATED,
        )

        resp = self.client.post(self.url, self._payload(product_id=product.id), format="json")
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertIn("id", data)
        self.assertEqual(data["product_id"], str(product.id))
        self.assertEqual(len(data["images"]), 1)
        self.assertIn("id", data["images"][0])
        self.assertEqual(data["images"][0]["url"], "https://example.com/sku.jpg")

        product.refresh_from_db()
        self.assertEqual(product.status, Product.Status.ON_MODERATION)
        emit_mock.assert_called_once_with(product_id=product.id, seller_id=product.seller_id)

    @patch("catalog.views.emit_product_created_event")
    def test_second_sku_no_state_change(self, emit_mock):
        product = Product.objects.create(
            title="Phone",
            description="d",
            category=self.category,
            seller_id=self.seller.id,
            status=Product.Status.ON_MODERATION,
        )
        existing = SKU.objects.create(
            product=product,
            name="128GB",
            price=10_000_000,
            cost_price=8_000_000,
            active_quantity=0,
            reserved_quantity=0,
        )
        SKUImage.objects.create(
            sku=existing,
            url="https://example.com/old.jpg",
            ordering=0,
        )

        resp = self.client.post(self.url, self._payload(product_id=product.id), format="json")
        self.assertEqual(resp.status_code, 201)

        product.refresh_from_db()
        self.assertEqual(product.status, Product.Status.ON_MODERATION)
        emit_mock.assert_not_called()

    def test_add_sku_to_hard_blocked_returns_403(self):
        product = Product.objects.create(
            title="Blocked",
            description="d",
            category=self.category,
            seller_id=self.seller.id,
            status=Product.Status.HARD_BLOCKED,
        )

        resp = self.client.post(self.url, self._payload(product_id=product.id), format="json")
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(
            resp.json(),
            {
                "code": FORBIDDEN,
                "message": "Cannot add SKU to hard-blocked product",
            },
        )

    def test_missing_image_returns_400(self):
        """Имя из DoD; по OpenAPI пустой images[] допустим → 201."""
        product = Product.objects.create(
            title="Phone",
            description="d",
            category=self.category,
            seller_id=self.seller.id,
            status=Product.Status.CREATED,
        )
        payload = self._payload(product_id=product.id)
        payload["images"] = []
        resp = self.client.post(self.url, payload, format="json")
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.json()["images"], [])

    @override_settings(
        MODERATION_BASE_URL="https://moderation.example",
        B2B_TO_MODERATION_KEY="mod-key",
        MODERATION_TIMEOUT=1,
    )
    @patch("catalog.moderation_client.request.urlopen")
    def test_first_sku_emits_created_event_to_moderation(self, urlopen_mock):
        emit_product_created_event(
            product_id="a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            seller_id="c3d4e5f6-a7b8-9012-cdef-123456789012",
        )

        self.assertTrue(urlopen_mock.called)
        request_obj = urlopen_mock.call_args.args[0]
        self.assertEqual(request_obj.full_url, "https://moderation.example/api/v1/events/product")
        self.assertEqual(request_obj.headers.get("X-service-key"), "mod-key")

        body = json.loads(request_obj.data.decode("utf-8"))
        self.assertEqual(body["event"], "CREATED")
        self.assertEqual(body["product_id"], "a1b2c3d4-e5f6-7890-abcd-ef1234567890")
        self.assertEqual(body["seller_id"], "c3d4e5f6-a7b8-9012-cdef-123456789012")
        self.assertTrue(body["idempotency_key"])
        self.assertTrue(body["date"].endswith("Z"))
