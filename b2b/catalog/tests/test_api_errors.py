from django.test import SimpleTestCase

from catalog.api_errors import VALIDATION_ERROR, drf_validation_error


class ApiErrorsTests(SimpleTestCase):
    def test_drf_validation_error_shape(self):
        body = drf_validation_error({"title": ["This field is required."]})
        self.assertEqual(body["code"], VALIDATION_ERROR)
        self.assertEqual(body["message"], "This field is required.")
        self.assertEqual(body["details"]["title"], "This field is required.")
