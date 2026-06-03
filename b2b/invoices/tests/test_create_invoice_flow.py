"""OpenAPI POST /api/v1/invoices — create-invoice flow (US-B2B-06)."""

from django.test import TestCase
from rest_framework.test import APIClient

from catalog.api_errors import NOT_OWNER, VALIDATION_ERROR
from catalog.models import Category, Product, SKU
from invoices.models import Invoice
from sellers.models import Seller


class CreateInvoiceFlowTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.seller = Seller.objects.create(
            email="invoice-seller@example.com",
            password="hashed",
            first_name="Inv",
            last_name="Seller",
            company_name="Inv Ltd",
        )
        self.other = Seller.objects.create(
            email="other-invoice@example.com",
            password="hashed",
            first_name="Other",
            last_name="Seller",
            company_name="Other Ltd",
        )
        self.category = Category.objects.create(name="Stock")
        self.moderated_product = Product.objects.create(
            title="Moderated item",
            description="Desc",
            category=self.category,
            seller_id=self.seller.id,
            status=Product.Status.MODERATED,
            slug="moderated-item",
        )
        self.moderated_sku = SKU.objects.create(
            product=self.moderated_product,
            name="Unit",
            price=5_000,
            active_quantity=1,
        )
        self.created_product = Product.objects.create(
            title="Draft",
            description="Desc",
            category=self.category,
            seller_id=self.seller.id,
            status=Product.Status.CREATED,
            slug="draft-item",
        )
        self.created_sku = SKU.objects.create(
            product=self.created_product,
            name="Draft SKU",
            price=3_000,
            active_quantity=0,
        )
        self.other_product = Product.objects.create(
            title="Other item",
            description="Desc",
            category=self.category,
            seller_id=self.other.id,
            status=Product.Status.MODERATED,
            slug="other-item",
        )
        self.other_sku = SKU.objects.create(
            product=self.other_product,
            name="Other unit",
            price=7_000,
            active_quantity=2,
        )
        self.url = "/api/v1/invoices"
        self.client.force_authenticate(user=self.seller)

    def test_create_invoice_with_moderated_sku_returns_201(self):
        payload = {
            "items": [
                {"sku_id": str(self.moderated_sku.id), "quantity": 10},
            ],
        }

        resp = self.client.post(self.url, payload, format="json")
        self.assertEqual(resp.status_code, 201)

        body = resp.json()
        self.assertEqual(body["status"], Invoice.Status.CREATED)
        self.assertEqual(body["seller_id"], str(self.seller.id))
        self.assertEqual(len(body["items"]), 1)
        item = body["items"][0]
        self.assertEqual(item["sku_id"], str(self.moderated_sku.id))
        self.assertEqual(item["quantity"], 10)
        self.assertEqual(item["accepted_quantity"], 0)
        self.assertIn("id", item)
        self.assertIn("created_at", body)
        self.assertIn("updated_at", body)

        invoice = Invoice.objects.get(pk=body["id"])
        self.assertEqual(invoice.status, Invoice.Status.CREATED)
        self.assertEqual(invoice.items.count(), 1)

        self.moderated_sku.refresh_from_db()
        self.assertEqual(self.moderated_sku.active_quantity, 1)

    def test_empty_items_returns_400(self):
        resp = self.client.post(self.url, {"items": []}, format="json")
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["code"], VALIDATION_ERROR)

    def test_non_moderated_sku_returns_400(self):
        payload = {
            "items": [
                {"sku_id": str(self.created_sku.id), "quantity": 5},
            ],
        }

        resp = self.client.post(self.url, payload, format="json")
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["code"], VALIDATION_ERROR)

    def test_others_sku_returns_403(self):
        payload = {
            "items": [
                {"sku_id": str(self.other_sku.id), "quantity": 1},
            ],
        }

        resp = self.client.post(self.url, payload, format="json")
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(resp.json()["code"], NOT_OWNER)
        self.assertEqual(Invoice.objects.count(), 0)
