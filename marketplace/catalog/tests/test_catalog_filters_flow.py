"""Канон b2c-1-catalog-filters: листинг, фасеты, sort, недоступность B2B."""

import uuid
from unittest.mock import patch

import pytest

from catalog.b2b_client import B2BClientError
from catalog.openapi import PAGINATED_CATALOG_REQUIRED
from catalog.request_parsing import OPENAPI_SORT_VALUES


def _product_row(*, product_id, category_id, title="Item"):
    return {
        "id": str(product_id),
        "title": title,
        "slug": title.lower(),
        "status": "MODERATED",
        "deleted": False,
        "category_id": str(category_id),
        "min_price": 10_000,
        "cover_image": "https://cdn.example.com/x.jpg",
    }


def _product_detail(*, product_id, category_id, color: str):
    return {
        "id": str(product_id),
        "title": "Item",
        "slug": "item",
        "status": "MODERATED",
        "deleted": False,
        "category_id": str(category_id),
        "description": "d",
        "characteristics": [{"id": str(uuid.uuid4()), "name": "color", "value": color}],
        "skus": [
            {
                "id": str(uuid.uuid4()),
                "price": 10_000,
                "active_quantity": 3,
                "stock_quantity": 3,
            }
        ],
        "images": [],
    }


@pytest.mark.django_db
def test_catalog_returns_filtered_sorted_products(client):
    cat_id = uuid.uuid4()
    product_id = uuid.uuid4()

    with patch("catalog.catalog_openapi_views.B2BClient") as MockB2B:
        inst = MockB2B.return_value
        inst.get_products.return_value = {
            "items": [_product_row(product_id=product_id, category_id=cat_id)],
            "total_count": 1,
            "limit": 20,
            "offset": 0,
        }
        inst.get_categories.return_value = [
            {"id": str(cat_id), "name": "Phones", "parent_id": None}
        ]

        response = client.get(
            "/api/v1/catalog/products",
            {
                "filter[category_id]": str(cat_id),
                "sort": "price_asc",
                "limit": 10,
                "offset": 5,
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert PAGINATED_CATALOG_REQUIRED <= set(data.keys())
    assert data["limit"] == 10
    assert data["offset"] == 5

    call_kwargs = MockB2B.return_value.get_products.call_args.kwargs
    assert call_kwargs["category_id"] == str(cat_id)
    assert call_kwargs["sort"] == "price_asc"
    assert call_kwargs["limit"] == 10
    assert call_kwargs["offset"] == 5


@pytest.mark.django_db
def test_facets_return_counts_per_filter_value(client):
    cat_id = uuid.uuid4()
    p1, p2, p3 = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()

    with patch("catalog.catalog_openapi_views.B2BClient") as MockB2B:
        inst = MockB2B.return_value
        inst.get_products.return_value = {
            "items": [
                _product_row(product_id=p1, category_id=cat_id),
                _product_row(product_id=p2, category_id=cat_id),
                _product_row(product_id=p3, category_id=cat_id),
            ],
            "total_count": 3,
            "limit": 100,
            "offset": 0,
        }
        inst.batch_public_products.return_value = [
            _product_detail(product_id=p1, category_id=cat_id, color="Red"),
            _product_detail(product_id=p2, category_id=cat_id, color="Red"),
            _product_detail(product_id=p3, category_id=cat_id, color="Blue"),
        ]

        response = client.get(
            "/api/v1/catalog/facets",
            {"filter[category_id]": str(cat_id)},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["total_count"] == 3
    assert len(data["category_id"]) == 1
    assert data["category_id"][0]["value"] == str(cat_id)
    assert data["category_id"][0]["count"] == 3

    color_values = {row["value"]: row["count"] for row in data["attributes"]["color"]}
    assert color_values == {"Red": 2, "Blue": 1}


@pytest.mark.django_db
def test_invalid_sort_returns_400(client):
    response = client.get("/api/v1/catalog/products", {"sort": "cheapest"})

    assert response.status_code == 400
    body = response.json()
    assert body["code"] == "VALIDATION_ERROR"
    assert "price_asc" in body["message"]
    assert set(body["details"]["sort"]) == OPENAPI_SORT_VALUES


@pytest.mark.django_db
def test_b2b_unavailable_returns_502(client):
    with patch("catalog.catalog_openapi_views.B2BClient") as MockB2B:
        MockB2B.return_value.get_products.side_effect = B2BClientError(
            503, "B2B unavailable"
        )
        response = client.get("/api/v1/catalog/products")

    assert response.status_code == 502
    assert response.json()["code"] == "SERVICE_UNAVAILABLE"
