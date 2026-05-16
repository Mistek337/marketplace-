"""OpenAPI: GET /api/v1/catalog/products/{product_id}/similar — только 200."""

import uuid
from unittest.mock import patch

import pytest

from catalog.b2b_client import B2BClientError
from catalog.openapi import CATALOG_PRODUCT_CARD_REQUIRED
from catalog.request_parsing import SIMILAR_LIMIT_DEFAULT, SIMILAR_LIMIT_MAX


@pytest.mark.django_db
def test_similar_returns_catalog_product_card_array(client):
    pid = uuid.uuid4()
    sim_id = uuid.uuid4()
    with patch("catalog.catalog_openapi_views.B2BClient") as MockB2B:
        inst = MockB2B.return_value
        inst.get_similar_products.return_value = [
            {
                "id": str(sim_id),
                "title": "Peer",
                "min_price": 20_000,
                "cover_image": "https://cdn.example.com/p.jpg",
            }
        ]
        response = client.get(f"/api/v1/catalog/products/{pid}/similar")

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert CATALOG_PRODUCT_CARD_REQUIRED <= set(data[0].keys())
    assert data[0]["name"] == "Peer"
    inst.get_similar_products.assert_called_once_with(pid, limit=SIMILAR_LIMIT_DEFAULT)
    inst.get_categories.assert_not_called()


@pytest.mark.django_db
def test_similar_default_limit_is_10(client):
    pid = uuid.uuid4()
    with patch("catalog.catalog_openapi_views.B2BClient") as MockB2B:
        inst = MockB2B.return_value
        inst.get_similar_products.return_value = []
        client.get(f"/api/v1/catalog/products/{pid}/similar")

    assert inst.get_similar_products.call_args.kwargs["limit"] == 10


@pytest.mark.django_db
def test_similar_clamps_limit_to_50(client):
    pid = uuid.uuid4()
    with patch("catalog.catalog_openapi_views.B2BClient") as MockB2B:
        inst = MockB2B.return_value
        inst.get_similar_products.return_value = []
        client.get(f"/api/v1/catalog/products/{pid}/similar?limit=999")

    assert inst.get_similar_products.call_args.kwargs["limit"] == SIMILAR_LIMIT_MAX


@pytest.mark.django_db
def test_similar_invalid_limit_uses_default(client):
    pid = uuid.uuid4()
    with patch("catalog.catalog_openapi_views.B2BClient") as MockB2B:
        inst = MockB2B.return_value
        inst.get_similar_products.return_value = []
        response = client.get(f"/api/v1/catalog/products/{pid}/similar?limit=abc")

    assert response.status_code == 200
    assert inst.get_similar_products.call_args.kwargs["limit"] == SIMILAR_LIMIT_DEFAULT


@pytest.mark.django_db
def test_similar_empty_list_returns_200(client):
    pid = uuid.uuid4()
    with patch("catalog.catalog_openapi_views.B2BClient") as MockB2B:
        MockB2B.return_value.get_similar_products.return_value = []
        response = client.get(f"/api/v1/catalog/products/{pid}/similar")

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.django_db
def test_similar_unknown_product_returns_200_empty_list(client):
    pid = uuid.uuid4()
    with patch("catalog.catalog_openapi_views.B2BClient") as MockB2B:
        MockB2B.return_value.get_similar_products.side_effect = B2BClientError(
            404, "not found"
        )
        response = client.get(f"/api/v1/catalog/products/{pid}/similar")

    assert response.status_code == 200
    assert response.json() == []
