from django.test import TestCase
from rest_framework.test import APIClient

from catalog.models import Category


class CategoryResponseTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_list_categories_returns_openapi_shape(self):
        root = Category.objects.create(name="Electronics", is_active=True)
        child = Category.objects.create(name="Phones", parent=root, is_active=True)

        resp = self.client.get("/api/v1/categories")
        self.assertEqual(resp.status_code, 200)

        by_id = {item["id"]: item for item in resp.json()}
        root_data = by_id[str(root.id)]
        child_data = by_id[str(child.id)]

        for key in ("id", "name", "parent_id", "level", "path", "is_active", "created_at"):
            self.assertIn(key, root_data, msg=f"missing {key} on root")
            self.assertIn(key, child_data, msg=f"missing {key} on child")

        self.assertEqual(root_data["level"], 0)
        self.assertEqual(root_data["path"], "electronics")
        self.assertIsInstance(root_data["path"], str)
        self.assertTrue(root_data["is_active"])

        self.assertEqual(child_data["level"], 1)
        self.assertEqual(child_data["path"], "electronics/phones")
        self.assertEqual(child_data["parent_id"], str(root.id))
