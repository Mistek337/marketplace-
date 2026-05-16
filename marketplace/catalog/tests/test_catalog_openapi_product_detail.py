"""Контракт OpenAPI: GET /api/v1/catalog/products/{product_id}."""

import uuid
from unittest.mock import patch

import pytest

from catalog.openapi import (
    ALLOWED_STATUS,
    CATALOG_PRODUCT_DETAIL_REQUIRED,
    CATALOG_SKU_REQUIRED,
    IMAGE_REF_REQUIRED,
)


@pytest.mark.django_db
def test_product_detail_only_allowed_status_codes(client):
    product_id = uuid.uuid4()
    b2b = {
        "id": str(product_id),
        "title": "X",
        "description": "d",
        "status": "MODERATED",
        "deleted": False,
        "images": [{"id": str(uuid.uuid4()), "url": "https://img/x.jpg", "ordering": 0}],
        "skus": [
            {
                "id": str(uuid.uuid4()),
                "price": 500,
                "active_quantity": 1,
            }
        ],
    }

    with patch("catalog.views.B2BClient") as MockB2B:
        b2b_client = MockB2B.return_value
        b2b_client.get_product.return_value = b2b
        b2b_client.get_categories.return_value = []
        ok = client.get(f"/api/v1/catalog/products/{product_id}")
        b2b_client.get_product.side_effect = __import__(
            "catalog.b2b_client", fromlist=["B2BClientError"]
        ).B2BClientError(404, "missing")
        missing = client.get(f"/api/v1/catalog/products/{product_id}")

    assert ok.status_code in ALLOWED_STATUS["get_product_detail"]
    assert missing.status_code in ALLOWED_STATUS["get_product_detail"]
    assert set(ALLOWED_STATUS["get_product_detail"]) == {200, 404}


@pytest.mark.django_db
def test_product_detail_openapi_required_fields(client):
    product_id = uuid.uuid4()
    image_id = uuid.uuid4()
    sku_id = uuid.uuid4()
    b2b = {
        "id": str(product_id),
        "title": "Phone",
        "slug": "phone-1",
        "description": "Desc",
        "status": "MODERATED",
        "deleted": False,
        "images": [{"id": str(image_id), "url": "https://cdn/p.jpg", "ordering": 0}],
        "characteristics": [{"name": "RAM", "value": "8GB"}],
        "skus": [
            {
                "id": str(sku_id),
                "name": "Default",
                "article": "DEF-1",
                "price": 10_000,
                "discount": 1_000,
                "active_quantity": 2,
                "images": [{"id": str(uuid.uuid4()), "url": "https://cdn/s.jpg", "ordering": 0}],
            }
        ],
    }

    with patch("catalog.views.B2BClient") as MockB2B:
        MockB2B.return_value.get_product.return_value = b2b
        MockB2B.return_value.get_categories.return_value = []
        data = client.get(f"/api/v1/catalog/products/{product_id}").json()

    assert CATALOG_PRODUCT_DETAIL_REQUIRED <= set(data.keys())
    assert isinstance(data["attributes"], dict)
    assert data["attributes"]["RAM"] == "8GB"
    assert data["min_price"] == 9_000
    assert data["has_stock"] is True

    sku = data["skus"][0]
    assert CATALOG_SKU_REQUIRED <= set(sku.keys())
    assert sku["price"] == 9_000
    assert sku["old_price"] == 10_000
    assert sku["sku_code"] == "DEF-1"
    assert IMAGE_REF_REQUIRED <= set(sku["images"][0].keys())
