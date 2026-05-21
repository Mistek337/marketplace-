import json
from unittest.mock import patch

from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from catalog.api_errors import NOT_FOUND, NOT_OWNER
from catalog.models import Category, ModerationOutboxEvent, Product, ProductCharacteristic, SKU
from sellers.models import Seller


class PatchProductSkuFlowTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.seller = Seller.objects.create(
            email="patch-seller@example.com",
            password="hashed",
            first_name="Patch",
            last_name="Seller",
            company_name="Patch Ltd",
        )
        self.client.force_authenticate(user=self.seller)
        self.category = Category.objects.create(name="Категория")

    def _product(self, *, status):
        return Product.objects.create(
            title="Phone",
            description="Desc",
            category=self.category,
            seller_id=self.seller.id,
            status=status,
        )

    @patch("catalog.views.emit_product_edited_event")
    def test_patch_product_moderated_transitions_to_on_moderation(self, emit_mock):
        product = self._product(status=Product.Status.MODERATED)
        resp = self.client.patch(
            f"/api/v1/products/{product.id}",
            {"title": "Phone Pro"},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        product.refresh_from_db()
        self.assertEqual(product.status, Product.Status.ON_MODERATION)
        self.assertEqual(resp.json()["title"], "Phone Pro")
        emit_mock.assert_called_once_with(product_id=product.id, seller_id=product.seller_id)

    @patch("catalog.views.emit_product_edited_event")
    def test_patch_product_created_does_not_emit_edited(self, emit_mock):
        product = self._product(status=Product.Status.CREATED)
        resp = self.client.patch(
            f"/api/v1/products/{product.id}",
            {"description": "New desc"},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        product.refresh_from_db()
        self.assertEqual(product.status, Product.Status.CREATED)
        emit_mock.assert_not_called()

    @patch("catalog.views.emit_product_edited_event")
    def test_patch_sku_blocked_transitions_product_to_on_moderation(self, emit_mock):
        product = self._product(status=Product.Status.BLOCKED)
        sku = SKU.objects.create(
            product=product,
            name="128GB",
            price=10_000_000,
            active_quantity=0,
            reserved_quantity=0,
        )
        resp = self.client.patch(
            f"/api/v1/skus/{sku.id}",
            {"price": 9_500_000},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        product.refresh_from_db()
        self.assertEqual(product.status, Product.Status.ON_MODERATION)
        self.assertEqual(resp.json()["price"], 9_500_000)
        emit_mock.assert_called_once_with(product_id=product.id, seller_id=product.seller_id)

    def test_patch_unknown_sku_returns_404_not_found(self):
        resp = self.client.patch(
            "/api/v1/skus/00000000-0000-0000-0000-000000000099",
            {"price": 1},
            format="json",
        )
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(
            resp.json(),
            {"code": NOT_FOUND, "message": "SKU not found"},
        )

    def test_patch_other_sellers_product_returns_not_owner(self):
        other = Seller.objects.create(
            email="patch-other@example.com",
            password="hashed",
            first_name="Other",
            last_name="Seller",
            company_name="Other Ltd",
        )
        product = Product.objects.create(
            title="Other phone",
            description="Desc",
            category=self.category,
            seller_id=other.id,
            status=Product.Status.MODERATED,
        )
        resp = self.client.patch(
            f"/api/v1/products/{product.id}",
            {"title": "Hacked"},
            format="json",
        )
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(
            resp.json(),
            {
                "code": NOT_OWNER,
                "message": "Product does not belong to the authenticated seller",
            },
        )

    def test_patch_product_invalid_token_returns_unauthorized(self):
        self.client.force_authenticate(user=None)
        product = self._product(status=Product.Status.CREATED)
        self.client.credentials(HTTP_AUTHORIZATION="Bearer not-a-jwt")
        resp = self.client.patch(
            f"/api/v1/products/{product.id}",
            {"title": "X"},
            format="json",
        )
        self.assertEqual(resp.status_code, 401)
        self.assertEqual(resp.json()["code"], "UNAUTHORIZED")
        self.assertEqual(resp.json()["message"], "Invalid token")

    def test_patch_product_null_characteristics_clears_list(self):
        product = self._product(status=Product.Status.CREATED)
        ProductCharacteristic.objects.create(product=product, name="Бренд", value="Apple")
        resp = self.client.patch(
            f"/api/v1/products/{product.id}",
            {"characteristics": None},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(product.characteristic_rows.count(), 0)

    @override_settings(
        MODERATION_BASE_URL="https://moderation.example",
        B2B_TO_MODERATION_KEY="mod-key",
        MODERATION_TIMEOUT=1,
    )
    @patch("catalog.moderation_client.request.urlopen")
    def test_emit_edited_writes_outbox_and_posts_to_moderation(self, urlopen_mock):
        from catalog.moderation_client import emit_product_edited_event

        emit_product_edited_event(
            product_id="a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            seller_id="c3d4e5f6-a7b8-9012-cdef-123456789012",
        )

        self.assertEqual(ModerationOutboxEvent.objects.count(), 1)
        outbox = ModerationOutboxEvent.objects.get()
        self.assertEqual(outbox.event, "EDITED")
        self.assertIsNotNone(outbox.idempotency_key)
        self.assertTrue(urlopen_mock.called)
        request_obj = urlopen_mock.call_args.args[0]
        self.assertEqual(request_obj.full_url, "https://moderation.example/api/v1/events/product")
        body = json.loads(request_obj.data.decode("utf-8"))
        self.assertEqual(body["event"], "EDITED")
        self.assertEqual(body["idempotency_key"], str(outbox.idempotency_key))
        self.assertEqual(body["product_id"], "a1b2c3d4-e5f6-7890-abcd-ef1234567890")
