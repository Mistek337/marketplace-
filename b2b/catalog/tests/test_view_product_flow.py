from django.test import TestCase
from rest_framework.test import APIClient

from catalog.models import Category, Product, ProductImage, SKU, SKUImage
from sellers.models import Seller


class ViewProductFlowTests(TestCase):
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
        )
        ProductImage.objects.create(product=p, url="https://example.com/img.jpg", ordering=0)
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

    def test_get_moderated_product_returns_full_payload(self):
        product = self._create_product(status=Product.Status.MODERATED, seller_id=self.seller.id)
        self.client.force_authenticate(user=self.seller)

        resp = self.client.get(f"/api/v1/products/{product.id}")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], Product.Status.MODERATED)
        self.assertFalse(data["blocked"])
        self.assertIsNone(data["blocking_reason"])
        self.assertEqual(data["field_reports"], [])
        self.assertTrue(len(data["skus"]) == 1)
        self.assertEqual(data["skus"][0]["cost_price"], 9_500_000)
        self.assertEqual(data["skus"][0]["reserved_quantity"], 2)

    def test_get_blocked_product_returns_blocking_reason_and_field_reports(self):
        product = self._create_product(status=Product.Status.BLOCKED, seller_id=self.seller.id)
        self.client.force_authenticate(user=self.seller)

        resp = self.client.get(f"/api/v1/products/{product.id}")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], Product.Status.BLOCKED)
        self.assertTrue(data["blocked"])
        self.assertIsInstance(data["blocking_reason"], dict)
        self.assertTrue(data["blocking_reason"]["title"])
        self.assertIsInstance(data["field_reports"], list)

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

    def test_get_invalid_uuid_returns_400(self):
        self.client.force_authenticate(user=self.seller)
        resp = self.client.get("/api/v1/products/not-a-uuid")
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(
            resp.json(),
            {"code": "INVALID_REQUEST", "message": "id must be a valid UUID"},
        )
