from django.test import SimpleTestCase

from catalog.validation_errors import validation_error_response


class ValidationErrorsTests(SimpleTestCase):
    def test_converts_flat_field_error(self):
        body = validation_error_response(
            {"title": ["This field is required."]},
            request_data={"description": "x"},
        )
        item = body["detail"][0]
        self.assertEqual(item["loc"], ["body", "title"])
        self.assertEqual(item["msg"], "This field is required.")
        self.assertEqual(item["type"], "value_error.missing")
        self.assertEqual(item["ctx"], {})

    def test_converts_nested_list_errors(self):
        body = validation_error_response(
            {"images": [{"url": ["This field is required."]}]},
            request_data={"images": [{}]},
        )
        item = body["detail"][0]
        self.assertEqual(item["loc"], ["body", "images", 0, "url"])
