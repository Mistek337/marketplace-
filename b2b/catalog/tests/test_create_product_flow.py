from django.test import TestCase
from rest_framework.test import APIClient

from catalog.models import Category, Product
from sellers.models import Seller


class CreateProductFlowTests(TestCase):
    """US-B2B-01: создание карточки товара (flows/b2b-flows.md#create-product)."""

    def setUp(self):
        self.client = APIClient()
        self.seller = Seller.objects.create(
            email="create-product-seller@example.com",
            password="hashed",
            first_name="Seller",
            last_name="One",
            company_name="NeoMarket Seller",
        )
        self.client.force_authenticate(user=self.seller)
        self.category = Category.objects.create(name="Смартфоны")
        self.url = "/api/v1/products/"

    def _payload(self):
        return {
            "title": "iPhone 15",
            "description": "Новый смартфон",
            "category_id": str(self.category.id),
            "images": [{"url": "https://example.com/iphone15.jpg", "ordering": 0}],
            "characteristics": [{"name": "Бренд", "value": "Apple"}],
        }

    def _assert_field_error(self, resp, *, field: str, message: str):
        self.assertEqual(resp.status_code, 400)
        data = resp.json()
        self.assertIn("detail", data)
        match = next(
            (item for item in data["detail"] if field in item["loc"] and item["msg"] == message),
            None,
        )
        self.assertIsNotNone(
            match,
            f"Expected detail for field {field!r} with msg {message!r}, got {data.get('detail')}",
        )

    def test_create_product_returns_201_with_created_status(self):
        resp = self.client.post(self.url, data=self._payload(), format="json")
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertEqual(data["status"], Product.Status.CREATED)
        self.assertEqual(data["seller_id"], str(self.seller.id))
        self.assertEqual(data["category_id"], str(self.category.id))
        self.assertEqual(len(data["images"]), 1)
        self.assertIn("id", data["images"][0])
        self.assertEqual(len(data["characteristics"]), 1)
        self.assertIn("id", data["characteristics"][0])
        self.assertEqual(data["skus"], [])
        self.assertIn("created_at", data)
        self.assertIn("updated_at", data)

    def test_seller_id_taken_from_jwt(self):
        payload = self._payload()
        payload["seller_id"] = "00000000-0000-0000-0000-000000000001"
        resp = self.client.post(self.url, data=payload, format="json")
        self.assertEqual(resp.status_code, 201)
        product = Product.objects.get(title="iPhone 15")
        self.assertEqual(str(product.seller_id), str(self.seller.id))

    def test_missing_images_returns_400(self):
        payload = self._payload()
        payload.pop("images")
        resp = self.client.post(self.url, data=payload, format="json")
        self._assert_field_error(resp, field="images", message="This field is required.")

    def test_missing_category_returns_400(self):
        payload = self._payload()
        payload.pop("category_id")
        resp = self.client.post(self.url, data=payload, format="json")
        self._assert_field_error(resp, field="category_id", message="This field is required.")

    def test_invalid_category_id_returns_400(self):
        payload = self._payload()
        payload["category_id"] = "not-a-uuid"
        resp = self.client.post(self.url, data=payload, format="json")
        self._assert_field_error(
            resp,
            field="category_id",
            message="category_id must be a valid UUID",
        )
