from django.test import TestCase
from rest_framework.test import APIClient

from sellers.models import Seller


class SellersMeTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.seller = Seller.objects.create(
            email="me-seller@example.com",
            password="hashed",
            first_name="Ivan",
            last_name="Seller",
            company_name="Neo Ltd",
        )
        self.client.force_authenticate(user=self.seller)

    def test_get_sellers_me_returns_profile(self):
        resp = self.client.get("/api/v1/sellers/me")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["email"], "me-seller@example.com")
        self.assertEqual(data["company_name"], "Neo Ltd")

    def test_get_sellers_me_without_auth_returns_unauthorized(self):
        self.client.force_authenticate(user=None)
        resp = self.client.get("/api/v1/sellers/me")
        self.assertEqual(resp.status_code, 401)
        self.assertEqual(resp.json()["code"], "UNAUTHORIZED")
