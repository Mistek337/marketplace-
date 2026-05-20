from django.test import TestCase
from rest_framework.test import APIClient

from catalog.models import Category, Product
from sellers.models import Seller


class CreateProductFlowTests(TestCase):
    """US-B2B-01 / OpenAPI POST /api/v1/products."""

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

    def _assert_validation_error(self, resp, *, field: str | None = None):
        self.assertEqual(resp.status_code, 422)
        data = resp.json()
        self.assertEqual(data["code"], "VALIDATION_ERROR")
        self.assertIn("message", data)
        self.assertIn("details", data)
        if field is not None:
            self.assertIn(field, data["details"])

    def _assert_product_response_shape(self, data):
        for key in (
            "id",
            "seller_id",
            "category_id",
            "title",
            "slug",
            "description",
            "status",
            "deleted",
            "blocking_reason_id",
            "moderator_comment",
            "images",
            "characteristics",
            "skus",
            "created_at",
            "updated_at",
        ):
            self.assertIn(key, data, msg=f"missing ProductResponse field: {key}")

    def test_create_product_returns_201_with_created_status(self):
        resp = self.client.post(self.url, data=self._payload(), format="json")
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self._assert_product_response_shape(data)
        self.assertEqual(data["status"], Product.Status.CREATED)
        self.assertEqual(data["seller_id"], str(self.seller.id))
        self.assertEqual(data["category_id"], str(self.category.id))
        self.assertEqual(data["deleted"], False)
        self.assertIsNone(data["blocking_reason_id"])
        self.assertIsNone(data["moderator_comment"])
        self.assertIn("slug", data)
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

    def test_missing_images_returns_422(self):
        payload = self._payload()
        payload.pop("images")
        resp = self.client.post(self.url, data=payload, format="json")
        self._assert_validation_error(resp, field="images")

    def test_empty_images_returns_422(self):
        payload = self._payload()
        payload["images"] = []
        resp = self.client.post(self.url, data=payload, format="json")
        self._assert_validation_error(resp, field="images")

    def test_post_products_without_auth_returns_unauthorized_shape(self):
        self.client.force_authenticate(user=None)
        resp = self.client.post(self.url, data=self._payload(), format="json")
        self.assertEqual(resp.status_code, 401)
        self.assertEqual(
            resp.json(),
            {"code": "UNAUTHORIZED", "message": "Authentication required"},
        )

    def test_post_products_invalid_token_returns_unauthorized_shape(self):
        self.client.force_authenticate(user=None)
        self.client.credentials(HTTP_AUTHORIZATION="Bearer not-a-jwt")
        resp = self.client.post(self.url, data=self._payload(), format="json")
        self.assertEqual(resp.status_code, 401)
        data = resp.json()
        self.assertEqual(data["code"], "UNAUTHORIZED")
        self.assertEqual(data["message"], "Invalid token")

    def test_missing_category_returns_422(self):
        payload = self._payload()
        payload.pop("category_id")
        resp = self.client.post(self.url, data=payload, format="json")
        self._assert_validation_error(resp, field="category_id")

    def test_invalid_category_id_returns_422(self):
        payload = self._payload()
        payload["category_id"] = "not-a-uuid"
        resp = self.client.post(self.url, data=payload, format="json")
        self._assert_validation_error(resp, field="category_id")
