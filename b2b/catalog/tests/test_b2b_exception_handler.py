from django.test import TestCase
from rest_framework.test import APIClient

from catalog.models import Category
from sellers.models import Seller


class B2BExceptionHandlerTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.category = Category.objects.create(name="Cat")
        Seller.objects.create(
            email="auth-test@example.com",
            password="hashed",
            first_name="A",
            last_name="B",
            company_name="C",
        )

    def test_seller_login_invalid_credentials_openapi_error(self):
        resp = self.client.post(
            "/api/v1/auth/login",
            data={"username": "auth-test@example.com", "password": "wrong"},
            format="json",
        )
        self.assertEqual(resp.status_code, 401)
        self.assertEqual(
            resp.json(),
            {"code": "UNAUTHORIZED", "message": "Invalid credentials"},
        )
