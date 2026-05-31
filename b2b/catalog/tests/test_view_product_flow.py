from django.test import TestCase
from rest_framework.test import APIClient

from catalog.models import BlockingReason, Category, Product, ProductCharacteristic, ProductImage, SKU, SKUImage
from sellers.models import Seller


class ViewProductFlowTests(TestCase):
    """OpenAPI GET /api/v1/products/{product_id} → ProductDetailResponse."""

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
        self.blocking_reason = BlockingReason.objects.create(
            id="00000000-0000-0000-0000-000000000001",
            title="Некорректное описание",
            comment="Исправьте описание товара",
        )

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

    def _assert_detail_shape(self, data):
        for key in (
            "id",
            "seller_id",
            "category_id",
            "title",
            "slug",
            "description",
            "status",
            "deleted",
            "images",
            "characteristics",
            "skus",
            "created_at",
            "updated_at",
            "blocked",
            "blocking_reason",
            "field_reports",
        ):
            self.assertIn(key, data)
        self.assertIn("cost_price", data["skus"][0])
        self.assertIn("reserved_quantity", data["skus"][0])
        self.assertNotIn("blocking_reason_id", data)

    def test_get_moderated_product_returns_full_payload(self):
        product = self._create_product(status=Product.Status.MODERATED, seller_id=self.seller.id)
        self.client.force_authenticate(user=self.seller)

        resp = self.client.get(f"/api/v1/products/{product.id}")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self._assert_detail_shape(data)
        self.assertEqual(data["status"], Product.Status.MODERATED)
        self.assertFalse(data["blocked"])
        self.assertIsNone(data["blocking_reason"])
        self.assertEqual(data["field_reports"], [])
        self.assertEqual(data["skus"][0]["cost_price"], 9_500_000)
        self.assertEqual(data["skus"][0]["reserved_quantity"], 2)

    def test_get_blocked_product_returns_blocking_reason_and_field_reports(self):
        product = self._create_product(status=Product.Status.BLOCKED, seller_id=self.seller.id)
        product.blocking_reason_id = self.blocking_reason.id
        product.moderator_comment = "Исправьте описание товара"
        product.field_reports = [
            {
                "field_name": "description",
                "sku_id": None,
                "comment": "Описание не соответствует товару",
            },
            {
                "field_path": "images[0]",
                "message": "Низкое качество фото",
            },
        ]
        product.save()
        self.client.force_authenticate(user=self.seller)

        resp = self.client.get(f"/api/v1/products/{product.id}")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self._assert_detail_shape(data)
        self.assertEqual(data["status"], Product.Status.BLOCKED)
        self.assertTrue(data["blocked"])
        self.assertIsNotNone(data["blocking_reason"])
        self.assertEqual(data["blocking_reason"]["title"], "Некорректное описание")
        self.assertEqual(len(data["field_reports"]), 2)
        self.assertEqual(data["field_reports"][0]["field_name"], "description")
        self.assertEqual(data["field_reports"][1]["field_name"], "images[0]")
        self.assertEqual(data["field_reports"][1]["comment"], "Низкое качество фото")

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
        resp = self.client.get("/api/v1/products/00000000-0000-0000-0000-000000000099")
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(
            resp.json(),
            {"code": "NOT_FOUND", "message": "Product not found"},
        )
