from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from catalog.models import Category, Product, ProductCharacteristic, ProductImage, SKU
from sellers.models import Seller


@override_settings(B2C_TO_B2B_KEY="test-b2c-key")
class PublicCatalogFlowTests(TestCase):
    """OpenAPI /api/v1/public/products — межсервисный каталог B2C."""

    def setUp(self):
        self.client = APIClient()
        self.list_url = "/api/v1/public/products/"
        self.batch_url = "/api/v1/public/products/batch/"
        self.category = Category.objects.create(name="Phones")
        self.seller_id = Seller.objects.create(
            email="catalog-seller@example.com",
            password="hashed",
            first_name="S",
            last_name="L",
            company_name="Co",
        ).id

    def _headers(self):
        return {"HTTP_X_SERVICE_KEY": "test-b2c-key"}

    def _create_product(self, *, status, active_quantity=5, deleted=False, title="Phone"):
        product = Product.objects.create(
            title=title,
            description="Desc",
            category=self.category,
            status=status,
            seller_id=self.seller_id,
            deleted=deleted,
            slug=title.lower().replace(" ", "-"),
        )
        ProductImage.objects.create(
            product=product,
            url=f"https://example.com/{title}.jpg",
            ordering=0,
        )
        SKU.objects.create(
            product=product,
            name="Default",
            price=10_000,
            cost_price=5_000,
            discount=0,
            active_quantity=active_quantity,
            reserved_quantity=1,
        )
        return product

    def test_catalog_returns_moderated_in_stock_products(self):
        visible = self._create_product(status=Product.Status.MODERATED, active_quantity=3)
        self._create_product(status=Product.Status.CREATED, active_quantity=3)
        self._create_product(status=Product.Status.MODERATED, active_quantity=0)

        resp = self.client.get(self.list_url, **self._headers())
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["total_count"], 1)
        self.assertEqual(len(data["items"]), 1)
        item = data["items"][0]
        self.assertEqual(str(item["id"]), str(visible.id))
        for key in (
            "id",
            "title",
            "slug",
            "status",
            "category_id",
            "min_price",
            "cover_image",
            "created_at",
        ):
            self.assertIn(key, item)
        self.assertEqual(item["status"], "MODERATED")
        self.assertEqual(item["min_price"], 10_000)
        self.assertIn("example.com", item["cover_image"])

    def test_catalog_excludes_hard_blocked(self):
        self._create_product(status=Product.Status.HARD_BLOCKED, active_quantity=5)
        self._create_product(status=Product.Status.MODERATED, active_quantity=5, title="Ok")

        resp = self.client.get(self.list_url, **self._headers())
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["total_count"], 1)
        self.assertEqual(resp.json()["items"][0]["title"], "Ok")

    def test_catalog_missing_service_key_returns_401(self):
        resp = self.client.get(self.list_url)
        self.assertEqual(resp.status_code, 401)
        self.assertEqual(resp.json()["code"], "UNAUTHORIZED")

    def test_catalog_response_has_no_cost_price(self):
        product = self._create_product(status=Product.Status.MODERATED, active_quantity=2)
        detail_url = f"/api/v1/public/products/{product.id}/"

        list_resp = self.client.get(self.list_url, **self._headers())
        self.assertEqual(list_resp.status_code, 200)

        detail_resp = self.client.get(detail_url, **self._headers())
        self.assertEqual(detail_resp.status_code, 200)
        sku = detail_resp.json()["skus"][0]
        self.assertNotIn("cost_price", sku)
        self.assertNotIn("reserved_quantity", sku)

        batch_resp = self.client.post(
            self.batch_url,
            {"product_ids": [str(product.id)]},
            format="json",
            **self._headers(),
        )
        self.assertEqual(batch_resp.status_code, 200)
        batch_sku = batch_resp.json()[0]["skus"][0]
        self.assertNotIn("cost_price", batch_sku)
        self.assertNotIn("reserved_quantity", batch_sku)

    def test_batch_ids_returns_visible_subset(self):
        visible = self._create_product(status=Product.Status.MODERATED, active_quantity=1, title="A")
        hidden = self._create_product(status=Product.Status.BLOCKED, active_quantity=1, title="B")
        missing_id = "00000000-0000-4000-8000-000000000099"

        resp = self.client.post(
            self.batch_url,
            {"product_ids": [str(visible.id), str(hidden.id), missing_id]},
            format="json",
            **self._headers(),
        )
        self.assertEqual(resp.status_code, 200)
        returned_ids = {row["id"] for row in resp.json()}
        self.assertEqual(returned_ids, {str(visible.id)})

    def test_public_similar_returns_short_items_from_same_category(self):
        anchor = self._create_product(
            status=Product.Status.MODERATED,
            active_quantity=2,
            title="Anchor",
        )
        peer = self._create_product(
            status=Product.Status.MODERATED,
            active_quantity=2,
            title="Peer",
        )
        other_category = Category.objects.create(name="Laptops")
        other_product = Product.objects.create(
            title="Other cat",
            description="Desc",
            category=other_category,
            status=Product.Status.MODERATED,
            seller_id=self.seller_id,
            slug="other-cat",
        )
        SKU.objects.create(
            product=other_product,
            name="Default",
            price=20_000,
            active_quantity=3,
        )

        url = f"/api/v1/public/products/{anchor.id}/similar/"
        resp = self.client.get(url, {"limit": 10}, **self._headers())
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIsInstance(data, list)
        ids = {row["id"] for row in data}
        self.assertIn(str(peer.id), ids)
        self.assertNotIn(str(anchor.id), ids)
        self.assertIn("min_price", data[0])

    def test_public_similar_fills_from_sibling_categories_when_few_in_anchor_category(self):
        parent = Category.objects.create(name="Electronics")
        anchor_category = Category.objects.create(name="Phones", parent=parent)
        sibling_category = Category.objects.create(name="Tablets", parent=parent)

        anchor = Product.objects.create(
            title="Anchor phone",
            description="Desc",
            category=anchor_category,
            status=Product.Status.MODERATED,
            seller_id=self.seller_id,
            slug="anchor-phone",
        )
        SKU.objects.create(
            product=anchor,
            name="Default",
            price=10_000,
            active_quantity=2,
        )
        peer = Product.objects.create(
            title="Peer phone",
            description="Desc",
            category=anchor_category,
            status=Product.Status.MODERATED,
            seller_id=self.seller_id,
            slug="peer-phone",
        )
        SKU.objects.create(
            product=peer,
            name="Default",
            price=11_000,
            active_quantity=2,
        )

        sibling_products = []
        for index in range(5):
            product = Product.objects.create(
                title=f"Tablet {index}",
                description="Desc",
                category=sibling_category,
                status=Product.Status.MODERATED,
                seller_id=self.seller_id,
                slug=f"tablet-{index}",
            )
            SKU.objects.create(
                product=product,
                name="Default",
                price=15_000 + index,
                active_quantity=3,
            )
            sibling_products.append(product)

        url = f"/api/v1/public/products/{anchor.id}/similar/"
        resp = self.client.get(url, {"limit": 8}, **self._headers())
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data), 6)

        returned_ids = {row["id"] for row in data}
        self.assertIn(str(peer.id), returned_ids)
        self.assertNotIn(str(anchor.id), returned_ids)
        sibling_ids = {str(product.id) for product in sibling_products}
        self.assertTrue(returned_ids & sibling_ids)

    def test_public_similar_missing_product_returns_404(self):
        missing = "00000000-0000-4000-8000-000000000099"
        url = f"/api/v1/public/products/{missing}/similar/"
        resp = self.client.get(url, **self._headers())
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(resp.json()["code"], "NOT_FOUND")

    def test_public_sku_returns_public_fields_only(self):
        product = self._create_product(status=Product.Status.MODERATED, active_quantity=2)
        sku = product.skus.first()
        url = f"/api/v1/public/skus/{sku.id}/"
        resp = self.client.get(url, **self._headers())
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(str(data["id"]), str(sku.id))
        self.assertNotIn("cost_price", data)
        self.assertNotIn("reserved_quantity", data)

    def test_public_sku_hidden_returns_404(self):
        product = self._create_product(status=Product.Status.BLOCKED, active_quantity=2)
        sku = product.skus.first()
        url = f"/api/v1/public/skus/{sku.id}/"
        resp = self.client.get(url, **self._headers())
        self.assertEqual(resp.status_code, 404)

    def test_public_list_invalid_sort_returns_422(self):
        resp = self.client.get(
            self.list_url,
            {"sort": "invalid_sort"},
            **self._headers(),
        )
        self.assertEqual(resp.status_code, 422)
        self.assertEqual(resp.json()["code"], "VALIDATION_ERROR")

    def test_public_list_product_public_response_shape(self):
        product = self._create_product(status=Product.Status.MODERATED, active_quantity=2)
        ProductCharacteristic.objects.create(
            product=product,
            name="Бренд",
            value="Apple",
        )
        url = f"/api/v1/public/products/{product.id}/"
        resp = self.client.get(url, **self._headers())
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        for key in (
            "id",
            "seller_id",
            "category_id",
            "title",
            "slug",
            "description",
            "status",
            "images",
            "characteristics",
            "skus",
            "created_at",
            "updated_at",
        ):
            self.assertIn(key, data)
        self.assertIn("id", data["images"][0])
        self.assertIn("id", data["characteristics"][0])
        sku_images = data["skus"][0]["images"]
        if sku_images:
            self.assertIn("id", sku_images[0])
