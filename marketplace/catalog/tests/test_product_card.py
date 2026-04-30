"""GET /api/v1/products/{id} — карточка для покупателя (B2C поверх B2B)."""

import uuid
from unittest.mock import patch

import pytest
from rest_framework.test import APIClient

from catalog.views import B2C_FORBIDDEN_SKU_FIELDS


def _moderated_product_b2b_payload(product_id, sku1_id, sku2_id, category_id):
    return {
        "id": str(product_id),
        "slug": "demo-phone",
        "title": "Demo Phone",
        "description": "Описание для витрины",
        "status": "MODERATED",
        "deleted": False,
        "category": {"id": str(category_id), "name": "Смартфоны"},
        "images": [{"url": "https://cdn.example.com/front.jpg", "ordering": 0}],
        "characteristics": [{"name": "Бренд", "value": "Demo"}],
        "skus": [
            {
                "id": str(sku1_id),
                "name": "128 GB Black",
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


@pytest.mark.django_db
def test_product_card_returns_full_data_with_skus(api_client):
    product_id = uuid.uuid4()
    sku1 = uuid.uuid4()
    sku2 = uuid.uuid4()
    cat = uuid.uuid4()
    b2b = _moderated_product_b2b_payload(product_id, sku1, sku2, cat)

    with patch("catalog.views.B2BClient") as MockB2B:
        MockB2B.return_value.get_product.return_value = b2b
        response = api_client.get(f"/api/v1/products/{product_id}")

    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Demo Phone"
    assert data["description"] == "Описание для витрины"
    assert data["slug"] == "demo-phone"
    assert data["status"] == "MODERATED"
    assert len(data["images"]) == 1
    assert data["images"][0]["url"] == "https://cdn.example.com/front.jpg"
    assert data["characteristics"][0]["name"] == "Бренд"
    assert len(data["skus"]) == 2
    s0 = data["skus"][0]
    assert s0["name"] == "128 GB Black"
    assert s0["price"] == 99_990_00
    assert s0["discount"] == 0
    assert s0["active_quantity"] == 3
    assert s0["in_stock"] is True
    s1 = data["skus"][1]
    assert s1["discount"] == 5_000_00
    assert s1["active_quantity"] == 0
    assert s1["in_stock"] is False


@pytest.mark.django_db
def test_cost_price_absent_in_response(api_client):
    product_id = uuid.uuid4()
    sku1 = uuid.uuid4()
    sku2 = uuid.uuid4()
    cat = uuid.uuid4()
    b2b = _moderated_product_b2b_payload(product_id, sku1, sku2, cat)

    with patch("catalog.views.B2BClient") as MockB2B:
        MockB2B.return_value.get_product.return_value = b2b
        response = api_client.get(f"/api/v1/products/{product_id}")

    assert response.status_code == 200
    body = response.json()
    assert "cost_price" not in body["skus"][0]
    assert "reserved_quantity" not in body["skus"][0]
    for sku in body["skus"]:
        assert not B2C_FORBIDDEN_SKU_FIELDS.intersection(sku.keys())


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
        response = api_client.get(f"/api/v1/products/{product_id}")

    assert response.status_code == 404
    assert response.json().get("message") == "Not found"


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
        response = api_client.get(f"/api/v1/products/{product_id}")

    assert response.status_code == 404


@pytest.mark.django_db
def test_sku_without_stock_is_shown_as_unavailable(api_client):
    product_id = uuid.uuid4()
    sku_id = uuid.uuid4()
    b2b = {
        "id": str(product_id),
        "slug": "x",
        "title": "One SKU",
        "description": "d",
        "status": "MODERATED",
        "deleted": False,
        "images": [],
        "characteristics": [],
        "category": {"id": str(uuid.uuid4()), "name": "C"},
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
        MockB2B.return_value.get_product.return_value = b2b
        response = api_client.get(f"/api/v1/products/{product_id}")

    assert response.status_code == 200
    sku = response.json()["skus"][0]
    assert sku["active_quantity"] == 0
    assert sku["in_stock"] is False
