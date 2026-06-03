"""OpenAPI GET /api/v1/products — listMyProducts (strict schema)."""

from django.test import TestCase
from rest_framework.test import APIClient

from catalog.api_errors import UNAUTHORIZED, VALIDATION_ERROR
from catalog.models import Category, Product, SKU
from sellers.models import Seller

OPENAPI_PRODUCT_SHORT_FIELDS = frozenset(
    {
        "id",
        "title",
        "slug",
        "status",
        "category_id",
        "deleted",
        "created_at",
        "min_price",
        "cover_image",
    }
)

OPENAPI_PAGINATED_FIELDS = frozenset({"items", "total_count", "limit", "offset"})


class ListProductsFlowTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.seller = Seller.objects.create(
            email="list-seller@example.com",
            password="hashed",
            first_name="List",
            last_name="Seller",
            company_name="List Ltd",
        )
        self.other = Seller.objects.create(
            email="other-list@example.com",
            password="hashed",
            first_name="Other",
            last_name="Seller",
            company_name="Other Ltd",
        )
        self.category = Category.objects.create(name="Electronics")
        self.url = "/api/v1/products"
        self.client.force_authenticate(user=self.seller)

    def _product(
        self,
        *,
        seller_id,
        title,
        status=Product.Status.MODERATED,
        deleted=False,
        slug=None,
    ) -> Product:
        return Product.objects.create(
            title=title,
            description="Desc",
            category=self.category,
            seller_id=seller_id,
            status=status,
            slug=slug or title.lower().replace(" ", "-"),
            deleted=deleted,
        )

    def test_list_returns_only_own_products(self):
        own = self._product(seller_id=self.seller.id, title="My Phone")
        SKU.objects.create(product=own, name="64GB", price=10_000, active_quantity=5)
        other = self._product(seller_id=self.other.id, title="Competitor Phone")
        SKU.objects.create(product=other, name="128GB", price=12_000, active_quantity=3)

        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(set(body.keys()), OPENAPI_PAGINATED_FIELDS)

        ids = {item["id"] for item in body["items"]}
        self.assertIn(str(own.id), ids)
        self.assertNotIn(str(other.id), ids)

        item = next(i for i in body["items"] if i["id"] == str(own.id))
        self.assertEqual(set(item.keys()), OPENAPI_PRODUCT_SHORT_FIELDS)
        self.assertEqual(item["min_price"], 10_000)

    def test_idor_query_param_seller_id_ignored(self):
        own = self._product(seller_id=self.seller.id, title="Mine")
        competitor = self._product(seller_id=self.other.id, title="Theirs")

        resp = self.client.get(self.url, {"seller_id": str(self.other.id)})
        self.assertEqual(resp.status_code, 200)
        ids = {item["id"] for item in resp.json()["items"]}
        self.assertIn(str(own.id), ids)
        self.assertNotIn(str(competitor.id), ids)

    def test_deleted_products_visible_with_deleted_flag(self):
        active = self._product(seller_id=self.seller.id, title="Active", deleted=False)
        removed = self._product(
            seller_id=self.seller.id,
            title="Removed",
            deleted=True,
            slug="removed",
        )

        without = self.client.get(self.url)
        self.assertEqual(without.status_code, 200)
        ids_default = {item["id"] for item in without.json()["items"]}
        self.assertIn(str(active.id), ids_default)
        self.assertNotIn(str(removed.id), ids_default)

        with_deleted = self.client.get(self.url, {"include_deleted": "true"})
        self.assertEqual(with_deleted.status_code, 200)
        by_id = {item["id"]: item for item in with_deleted.json()["items"]}
        self.assertIn(str(removed.id), by_id)
        self.assertTrue(by_id[str(removed.id)]["deleted"])

    def test_status_filter_works_correctly(self):
        moderated = self._product(
            seller_id=self.seller.id,
            title="Mod",
            status=Product.Status.MODERATED,
            slug="mod",
        )
        blocked = self._product(
            seller_id=self.seller.id,
            title="Blocked",
            status=Product.Status.BLOCKED,
            slug="blocked",
        )

        resp = self.client.get(self.url, {"status": Product.Status.BLOCKED})
        self.assertEqual(resp.status_code, 200)
        ids = {item["id"] for item in resp.json()["items"]}
        self.assertIn(str(blocked.id), ids)
        self.assertNotIn(str(moderated.id), ids)
        for item in resp.json()["items"]:
            self.assertEqual(item["status"], Product.Status.BLOCKED)

    def test_invalid_status_returns_422(self):
        resp = self.client.get(self.url, {"status": "NOT_A_STATUS"})
        self.assertEqual(resp.status_code, 422)
        self.assertEqual(resp.json()["code"], VALIDATION_ERROR)

    def test_unauthenticated_returns_401(self):
        self.client.force_authenticate(user=None)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 401)
        self.assertEqual(resp.json()["code"], UNAUTHORIZED)
