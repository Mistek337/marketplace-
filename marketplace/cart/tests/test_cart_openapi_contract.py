import json
import uuid

import pytest

from cart.openapi import (
    ALLOWED_STATUS,
    CART_ITEM_REQUIRED,
    CART_RESPONSE_REQUIRED,
    CART_VALIDATION_ISSUE_TYPES,
    CART_VALIDATION_RESPONSE_REQUIRED,
)


def _product(product_id, sku_id, **kwargs):
    base = {
        "id": str(product_id),
        "title": "Item",
        "status": "MODERATED",
        "deleted": False,
        "images": [{"id": str(uuid.uuid4()), "url": "https://img/x.jpg", "ordering": 0}],
        "skus": [
            {
                "id": str(sku_id),
                "name": "Default",
                "sku_code": "A-1",
                "price": 1000,
                "active_quantity": 3,
                "images": [],
            }
        ],
    }
    base.update(kwargs)
    return base


def _install_b2b(monkeypatch, product):
    sku = product["skus"][0]

    class FakeB2BClient:
        def get_public_sku(self, sku_id):
            return {
                "id": str(sku["id"]),
                "product_id": str(product["id"]),
                "price": sku["price"],
                "active_quantity": sku["active_quantity"],
            }

        def get_product(self, product_id):
            assert str(product_id) == str(product["id"])
            return product

        def batch_public_products(self, product_ids):
            if str(product["id"]) in {str(x) for x in product_ids}:
                return [product]
            return []

    monkeypatch.setattr("cart.services.B2BClient", FakeB2BClient)


@pytest.mark.django_db
def test_cart_response_matches_openapi_shape(client, monkeypatch):
    product_id = uuid.uuid4()
    sku_id = uuid.uuid4()
    product = _product(product_id, sku_id)
    _install_b2b(monkeypatch, product)

    session_id = uuid.uuid4()
    client.defaults["HTTP_X_SESSION_ID"] = str(session_id)
    client.post(
        "/api/v1/cart/items",
        data=json.dumps({"sku_id": str(sku_id), "quantity": 1}),
        content_type="application/json",
    )

    data = client.get("/api/v1/cart").json()
    assert CART_RESPONSE_REQUIRED <= set(data.keys())
    assert data["items_count"] == 1
    assert data["subtotal"] == 1000
    assert data["is_valid"] is True

    item = data["items"][0]
    assert CART_ITEM_REQUIRED <= set(item.keys())
    assert item["sku_code"] == "A-1"
    assert item["unit_price_at_add"] == 1000


@pytest.mark.django_db
def test_rejects_user_id_in_body(client, monkeypatch):
    product_id = uuid.uuid4()
    sku_id = uuid.uuid4()
    _install_b2b(monkeypatch, _product(product_id, sku_id))

    r = client.post(
        "/api/v1/cart/items",
        data=json.dumps(
            {"sku_id": str(sku_id), "quantity": 1, "user_id": str(uuid.uuid4())}
        ),
        content_type="application/json",
        HTTP_X_SESSION_ID=str(uuid.uuid4()),
    )
    assert r.status_code in ALLOWED_STATUS["post_items"]
    assert r.status_code == 400


@pytest.mark.django_db
def test_validation_response_matches_openapi(client, monkeypatch):
    product_id = uuid.uuid4()
    sku_id = uuid.uuid4()
    product = _product(product_id, sku_id, status="BLOCKED")
    _install_b2b(monkeypatch, product)

    session_id = uuid.uuid4()
    from cart.models import Cart, CartItem

    cart = Cart.objects.create(session_id=session_id, user=None)
    CartItem.objects.create(
        cart=cart,
        sku_id=sku_id,
        product_id=product_id,
        quantity=1,
        unit_price_at_add=1000,
    )

    client.defaults["HTTP_X_SESSION_ID"] = str(session_id)
    r = client.post("/api/v1/cart/validate")
    assert r.status_code in ALLOWED_STATUS["post_validate"]
    body = r.json()
    assert CART_VALIDATION_RESPONSE_REQUIRED <= set(body.keys())
    assert body["issues"][0]["type"] == "PRODUCT_BLOCKED"
    assert {i["type"] for i in body["issues"]} <= CART_VALIDATION_ISSUE_TYPES


@pytest.mark.django_db
def test_get_cart_invalid_session_header_returns_200(client):
    r = client.get("/api/v1/cart", HTTP_X_SESSION_ID="not-a-uuid")
    assert r.status_code in ALLOWED_STATUS["get_cart"]
    assert r.status_code == 200
    assert "id" in r.json()


@pytest.mark.django_db
def test_patch_unknown_sku_returns_200_not_404(client, monkeypatch):
    product_id = uuid.uuid4()
    sku_id = uuid.uuid4()
    _install_b2b(monkeypatch, _product(product_id, sku_id))

    session_id = uuid.uuid4()
    client.defaults["HTTP_X_SESSION_ID"] = str(session_id)

    r = client.patch(
        f"/api/v1/cart/items/{uuid.uuid4()}",
        data=json.dumps({"quantity": 1}),
        content_type="application/json",
    )
    assert r.status_code in ALLOWED_STATUS["patch_item"]
    assert r.status_code == 200


@pytest.mark.django_db
def test_patch_insufficient_stock_returns_409(client, monkeypatch):
    product_id = uuid.uuid4()
    sku_id = uuid.uuid4()
    _install_b2b(monkeypatch, _product(product_id, sku_id, active_quantity=1))

    session_id = uuid.uuid4()
    client.defaults["HTTP_X_SESSION_ID"] = str(session_id)
    client.post(
        "/api/v1/cart/items",
        data=json.dumps({"sku_id": str(sku_id), "quantity": 1}),
        content_type="application/json",
    )

    r = client.patch(
        f"/api/v1/cart/items/{sku_id}",
        data=json.dumps({"quantity": 5}),
        content_type="application/json",
    )
    assert r.status_code in ALLOWED_STATUS["patch_item"]
    assert r.status_code == 409
    assert r.json()["code"] == "CONFLICT"
