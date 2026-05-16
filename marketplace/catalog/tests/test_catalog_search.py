"""OpenAPI: GET /api/v1/catalog/products?q=... (US-CAT-02)."""

import uuid
from unittest.mock import patch

import pytest

from catalog.openapi import PAGINATED_CATALOG_REQUIRED


def _moderated_product(*, product_id, title="Coffee Maker", description="Hot coffee"):
    return {
        "id": str(product_id),
        "title": title,
        "description": description,
        "slug": "coffee-maker",
        "status": "MODERATED",
        "deleted": False,
        "category_id": str(uuid.uuid4()),
        "min_price": 3_500_00,
        "cover_image": "https://cdn.example.com/coffee.jpg",
    }


@pytest.mark.django_db
def test_search_returns_matching_products(client):
    product_id = uuid.uuid4()
    b2b_items = [_moderated_product(product_id=product_id, title="Coffee", description="Arabica")]

    with patch("catalog.catalog_openapi_views.B2BClient") as MockB2B:
        inst = MockB2B.return_value
        inst.get_products.return_value = {
            "items": b2b_items,
            "total_count": 1,
            "limit": 20,
            "offset": 0,
        }
        inst.get_categories.return_value = []
        response = client.get("/api/v1/catalog/products?q=coffee")

    assert response.status_code == 200
    data = response.json()
    assert PAGINATED_CATALOG_REQUIRED <= set(data.keys())
    assert data["total_count"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["name"] == "Coffee"
    inst.get_products.assert_called_once()
    assert inst.get_products.call_args.kwargs["search"] == "coffee"


@pytest.mark.django_db
def test_short_query_returns_400(client):
    with patch("catalog.catalog_openapi_views.B2BClient") as MockB2B:
        response = client.get("/api/v1/catalog/products?q=ab")

    assert response.status_code == 400
    body = response.json()
    assert body["code"] == "VALIDATION_ERROR"
    assert "3" in body["message"]
    MockB2B.return_value.get_products.assert_not_called()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "query",
    [
        "iPhone%15",
        "кофе'",
        "100%_off",
    ],
)
def test_special_chars_do_not_break_query(client, query):
    with patch("catalog.catalog_openapi_views.B2BClient") as MockB2B:
        inst = MockB2B.return_value
        inst.get_products.return_value = {
            "items": [],
            "total_count": 0,
            "limit": 20,
            "offset": 0,
        }
        inst.get_categories.return_value = []
        response = client.get("/api/v1/catalog/products", {"q": query})

    assert response.status_code == 200
    inst.get_products.assert_called_once()
    assert inst.get_products.call_args.kwargs["search"] == query


@pytest.mark.django_db
def test_search_with_category_filter(client):
    cat_id = uuid.uuid4()
    with patch("catalog.catalog_openapi_views.B2BClient") as MockB2B:
        inst = MockB2B.return_value
        inst.get_products.return_value = {
            "items": [],
            "total_count": 0,
            "limit": 20,
            "offset": 0,
        }
        inst.get_categories.return_value = []
        response = client.get(
            f"/api/v1/catalog/products?q=phone&filter[category_id]={cat_id}"
        )

    assert response.status_code == 200
    kwargs = inst.get_products.call_args.kwargs
    assert kwargs["search"] == "phone"
    assert kwargs["category_id"] == str(cat_id)


@pytest.mark.django_db
def test_empty_results_returns_200(client):
    with patch("catalog.catalog_openapi_views.B2BClient") as MockB2B:
        inst = MockB2B.return_value
        inst.get_products.return_value = {
            "items": [],
            "total_count": 0,
            "limit": 20,
            "offset": 0,
        }
        inst.get_categories.return_value = []
        response = client.get("/api/v1/catalog/products?q=zzznonexistent")

    assert response.status_code == 200
    data = response.json()
    assert data["items"] == []
    assert data["total_count"] == 0
