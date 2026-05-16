"""OpenAPI: листинг и категории каталога."""

import uuid
from unittest.mock import patch

import pytest

from catalog.openapi import (
    CATALOG_PRODUCT_CARD_REQUIRED,
    CATEGORY_REF_REQUIRED,
    PAGINATED_CATALOG_REQUIRED,
)


@pytest.mark.django_db
def test_catalog_products_list_openapi_shape(client):
    product_id = uuid.uuid4()
    cat_id = uuid.uuid4()
    b2b_items = [
        {
            "id": str(product_id),
            "title": "Phone",
            "slug": "phone",
            "status": "MODERATED",
            "deleted": False,
            "category_id": str(cat_id),
            "min_price": 50_000,
            "cover_image": "https://cdn.example.com/p.jpg",
        }
    ]

    with patch("catalog.catalog_openapi_views.B2BClient") as MockB2B:
        inst = MockB2B.return_value
        inst.get_products.return_value = {
            "items": b2b_items,
            "total_count": 1,
            "limit": 20,
            "offset": 0,
        }
        inst.get_categories.return_value = [
            {"id": str(cat_id), "name": "Phones", "parent_id": None}
        ]
        response = client.get("/api/v1/catalog/products?limit=20&offset=0")

    assert response.status_code == 200
    data = response.json()
    assert PAGINATED_CATALOG_REQUIRED <= set(data.keys())
    assert len(data["items"]) == 1
    card = data["items"][0]
    assert CATALOG_PRODUCT_CARD_REQUIRED <= set(card.keys())
    assert card["name"] == "Phone"
    assert card["min_price"] == 50_000
    assert card["has_stock"] is True


@pytest.mark.django_db
def test_catalog_categories_flat(client):
    cat_id = uuid.uuid4()
    with patch("catalog.catalog_openapi_views.B2BClient") as MockB2B:
        MockB2B.return_value.get_categories.return_value = [
            {"id": str(cat_id), "name": "Root", "parent_id": None}
        ]
        response = client.get("/api/v1/catalog/categories")

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert CATEGORY_REF_REQUIRED <= set(data[0].keys())


@pytest.mark.django_db
def test_catalog_similar_returns_card_array(client):
    pid = uuid.uuid4()
    sim_id = uuid.uuid4()
    with patch("catalog.catalog_openapi_views.B2BClient") as MockB2B:
        inst = MockB2B.return_value
        inst.get_product.return_value = {
            "id": str(pid),
            "title": "A",
            "status": "MODERATED",
            "deleted": False,
            "skus": [{"id": str(uuid.uuid4()), "price": 100, "active_quantity": 1}],
        }
        inst.get_similar_products.return_value = [
            {
                "id": str(sim_id),
                "title": "B",
                "min_price": 200,
                "cover_image": "https://cdn/x.jpg",
            }
        ]
        response = client.get(f"/api/v1/catalog/products/{pid}/similar?limit=5")

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert data[0]["name"] == "B"
