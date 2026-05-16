from django.test import TestCase
from rest_framework.test import APIClient

from catalog.models import Category, Product, ProductCharacteristic, ProductImage, SKU, SKUImage
from sellers.models import Seller


class ViewProductFlowTests(TestCase):
    """OpenAPI GET /api/v1/products/{product_id} → ProductResponse."""

    def setUp(self):
        self.client = APIClient()
        self.seller = Seller.objects.create(
            email="seller-view@example.com",
            password="hashed",
            first_name="Seller",
            last_name="Owner",
            company_name="Owner Ltd",
        )
        self.other = Seller.objects.create(
            email="seller-other@example.com",
            password="hashed",
            first_name="Other",
            last_name="Seller",
            company_name="Other Ltd",
        )
        self.category = Category.objects.create(name="Phones")

    def _create_product(self, *, status, seller_id):
        p = Product.objects.create(
            title="Phone",
            description="Desc",
            category=self.category,
            status=status,
            seller_id=seller_id,
            deleted=False,
            slug="phone",
        )
        ProductImage.objects.create(product=p, url="https://example.com/img.jpg", ordering=0)
        ProductCharacteristic.objects.create(product=p, name="Бренд", value="Apple")
        sku = SKU.objects.create(
            product=p,
            name="256GB Black",
            price=12_999_000,
            cost_price=9_500_000,
            discount=0,
            active_quantity=10,
            reserved_quantity=2,
        )
        SKUImage.objects.create(
            sku=sku,
            url="https://example.com/sku.jpg",
            ordering=0,
        )
        return p

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
            self.assertIn(key, data)
        self.assertIn("id", data["images"][0])
        self.assertIn("id", data["characteristics"][0])
        self.assertIn("id", data["skus"][0])
        self.assertIn("cost_price", data["skus"][0])
        self.assertIn("reserved_quantity", data["skus"][0])

    def test_get_moderated_product_returns_product_response(self):
        product = self._create_product(status=Product.Status.MODERATED, seller_id=self.seller.id)
        self.client.force_authenticate(user=self.seller)

        resp = self.client.get(f"/api/v1/products/{product.id}")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self._assert_product_response_shape(data)
        self.assertEqual(data["status"], Product.Status.MODERATED)
        self.assertEqual(data["category_id"], str(self.category.id))
        self.assertIsNone(data["blocking_reason_id"])
        self.assertIsNone(data["moderator_comment"])
        self.assertEqual(data["skus"][0]["cost_price"], 9_500_000)
        self.assertEqual(data["skus"][0]["reserved_quantity"], 2)

    def test_get_blocked_product_returns_product_response(self):
        product = self._create_product(status=Product.Status.BLOCKED, seller_id=self.seller.id)
        product.blocking_reason_id = "00000000-0000-0000-0000-000000000001"
        product.moderator_comment = "Fix description"
        product.save()
        self.client.force_authenticate(user=self.seller)

        resp = self.client.get(f"/api/v1/products/{product.id}")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], Product.Status.BLOCKED)
        self.assertEqual(data["blocking_reason_id"], "00000000-0000-0000-0000-000000000001")
        self.assertEqual(data["moderator_comment"], "Fix description")

    def test_get_others_product_returns_404(self):
        product = self._create_product(status=Product.Status.MODERATED, seller_id=self.other.id)
        self.client.force_authenticate(user=self.seller)

        resp = self.client.get(f"/api/v1/products/{product.id}")
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(
            resp.json(),
            {"code": "NOT_FOUND", "message": "Product not found"},
        )

    def test_get_nonexistent_returns_404(self):
        self.client.force_authenticate(user=self.seller)
        resp = self.client.get("/api/v1/products/00000000-0000-0000-0000-000000000001")
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(
            resp.json(),
            {"code": "NOT_FOUND", "message": "Product not found"},
        )

    def test_get_invalid_uuid_returns_404(self):
        self.client.force_authenticate(user=self.seller)
        resp = self.client.get("/api/v1/products/not-a-uuid")
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(
            resp.json(),
            {"code": "NOT_FOUND", "message": "Product not found"},
        )
