"""GET /api/v1/catalog/products/{product_id} — карточка для покупателя (OpenAPI)."""

import uuid
from unittest.mock import patch

import pytest
from rest_framework.test import APIClient

from catalog.openapi import (
    B2C_FORBIDDEN_SKU_FIELDS,
    CATALOG_PRODUCT_DETAIL_REQUIRED,
    CATALOG_SKU_REQUIRED,
    CATEGORY_REF_REQUIRED,
    IMAGE_REF_REQUIRED,
)


def _moderated_product_b2b_payload(product_id, sku1_id, sku2_id, category_id):
    return {
        "id": str(product_id),
        "slug": "demo-phone",
        "title": "Demo Phone",
        "description": "Описание для витрины",
        "status": "MODERATED",
        "deleted": False,
        "category_id": str(category_id),
        "images": [
            {
                "id": str(uuid.uuid4()),
                "url": "https://cdn.example.com/front.jpg",
                "ordering": 0,
            }
        ],
        "characteristics": [{"name": "Бренд", "value": "Demo"}],
        "skus": [
            {
                "id": str(sku1_id),
                "name": "128 GB Black",
                "article": "BLK-128",
                "price": 99_990_00,
                "discount": 0,
                "image": "https://cdn.example.com/black.jpg",
                "active_quantity": 3,
                "cost_price": 50_000_00,
                "reserved_quantity": 1,
                "characteristics": [{"name": "Цвет", "value": "Чёрный"}],
            },
            {
                "id": str(sku2_id),
                "name": "256 GB White",
                "article": "WHT-256",
                "price": 129_990_00,
                "discount": 5_000_00,
                "image": None,
                "active_quantity": 0,
                "cost_price": 80_000_00,
                "reserved_quantity": 0,
                "characteristics": [],
            },
        ],
    }


@pytest.fixture
def api_client():
    return APIClient()


def _categories_flat(category_id, name="Смартфоны"):
    return [{"id": str(category_id), "name": name, "parent_id": None}]


@pytest.mark.django_db
def test_product_card_returns_full_data_with_skus(api_client):
    product_id = uuid.uuid4()
    sku1 = uuid.uuid4()
    sku2 = uuid.uuid4()
    cat = uuid.uuid4()
    b2b = _moderated_product_b2b_payload(product_id, sku1, sku2, cat)

    with patch("catalog.views.B2BClient") as MockB2B:
        client = MockB2B.return_value
        client.get_product.return_value = b2b
        client.get_categories.return_value = _categories_flat(cat)
        response = api_client.get(f"/api/v1/catalog/products/{product_id}")

    assert response.status_code == 200
    data = response.json()
    assert CATALOG_PRODUCT_DETAIL_REQUIRED <= set(data.keys())
    assert data["name"] == "Demo Phone"
    assert data["description"] == "Описание для витрины"
    assert data["slug"] == "demo-phone"
    assert data["has_stock"] is True
    assert data["min_price"] == 99_990_00
    assert len(data["images"]) >= 1
    assert IMAGE_REF_REQUIRED <= set(data["images"][0].keys())
    assert data["attributes"]["Бренд"] == "Demo"
    assert CATEGORY_REF_REQUIRED <= set(data["category"].keys())
    assert data["category"]["name"] == "Смартфоны"

    assert len(data["skus"]) == 2
    s0 = data["skus"][0]
    assert CATALOG_SKU_REQUIRED <= set(s0.keys())
    assert s0["name"] == "128 GB Black"
    assert s0["sku_code"] == "BLK-128"
    assert s0["price"] == 99_990_00
    assert "old_price" not in s0
    assert s0["available_quantity"] == 3

    s1 = data["skus"][1]
    assert s1["price"] == 129_990_00 - 5_000_00
    assert s1["old_price"] == 129_990_00
    assert s1["available_quantity"] == 0


@pytest.mark.django_db
def test_cost_price_absent_in_response(api_client):
    product_id = uuid.uuid4()
    sku1 = uuid.uuid4()
    sku2 = uuid.uuid4()
    cat = uuid.uuid4()
    b2b = _moderated_product_b2b_payload(product_id, sku1, sku2, cat)

    with patch("catalog.views.B2BClient") as MockB2B:
        client = MockB2B.return_value
        client.get_product.return_value = b2b
        client.get_categories.return_value = _categories_flat(cat)
        response = api_client.get(f"/api/v1/catalog/products/{product_id}")

    assert response.status_code == 200
    body = response.json()
    for sku in body["skus"]:
        assert not B2C_FORBIDDEN_SKU_FIELDS.intersection(sku.keys())
        assert "discount" not in sku
        assert "active_quantity" not in sku


@pytest.mark.django_db
def test_blocked_product_returns_404(api_client):
    product_id = uuid.uuid4()
    b2b = {
        "id": str(product_id),
        "title": "Hidden",
        "description": "",
        "status": "DRAFT",
        "deleted": False,
        "skus": [],
    }

    with patch("catalog.views.B2BClient") as MockB2B:
        MockB2B.return_value.get_product.return_value = b2b
        response = api_client.get(f"/api/v1/catalog/products/{product_id}")

    assert response.status_code == 404
    assert response.json() == {"code": "NOT_FOUND", "message": "Product not found"}


@pytest.mark.django_db
def test_blocked_deleted_product_returns_404(api_client):
    product_id = uuid.uuid4()
    b2b = {
        "id": str(product_id),
        "title": "Deleted",
        "status": "MODERATED",
        "deleted": True,
        "skus": [],
    }

    with patch("catalog.views.B2BClient") as MockB2B:
        MockB2B.return_value.get_product.return_value = b2b
        response = api_client.get(f"/api/v1/catalog/products/{product_id}")

    assert response.status_code == 404
    assert response.json()["code"] == "NOT_FOUND"


@pytest.mark.django_db
def test_sku_without_stock_is_shown_as_unavailable(api_client):
    product_id = uuid.uuid4()
    sku_id = uuid.uuid4()
    cat = uuid.uuid4()
    b2b = {
        "id": str(product_id),
        "slug": "x",
        "title": "One SKU",
        "description": "d",
        "status": "MODERATED",
        "deleted": False,
        "images": [],
        "characteristics": [],
        "category_id": str(cat),
        "skus": [
            {
                "id": str(sku_id),
                "name": "Only variant",
                "price": 1000,
                "discount": 0,
                "active_quantity": 0,
                "characteristics": [],
            }
        ],
    }

    with patch("catalog.views.B2BClient") as MockB2B:
        client = MockB2B.return_value
        client.get_product.return_value = b2b
        client.get_categories.return_value = _categories_flat(cat, name="C")
        response = api_client.get(f"/api/v1/catalog/products/{product_id}")

    assert response.status_code == 200
    data = response.json()
    assert data["has_stock"] is False
    sku = data["skus"][0]
    assert sku["available_quantity"] == 0

