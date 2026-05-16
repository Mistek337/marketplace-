import json
import uuid

import pytest
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import RefreshToken

from cart.models import Cart, CartItem


User = get_user_model()


def _product_payload(*, product_id, sku_id, title="Phone", price=19900, active_quantity=5):
    return {
        "id": str(product_id),
        "title": title,
        "status": "MODERATED",
        "images": [{"id": str(uuid.uuid4()), "url": "https://img/p.jpg", "ordering": 0}],
        "skus": [
            {
                "id": str(sku_id),
                "name": "128GB",
                "article": "SKU-1",
                "price": price,
                "active_quantity": active_quantity,
                "images": [],
            }
        ],
    }


def _install_fake_b2b(monkeypatch, *, product_id, sku_id, **product_kwargs):
    product = _product_payload(product_id=product_id, sku_id=sku_id, **product_kwargs)

    class FakeB2BClient:
        def get_public_sku(self, sku_id_arg):
            assert str(sku_id_arg) == str(sku_id)
            sku = product["skus"][0]
            return {
                "id": str(sku_id),
                "product_id": str(product_id),
                "price": sku["price"],
                "active_quantity": sku["active_quantity"],
            }

        def get_product(self, product_id_arg):
            assert str(product_id_arg) == str(product_id)
            return product

        def batch_public_products(self, product_ids):
            if str(product_id) in {str(pid) for pid in product_ids}:
                return [product]
            return []

    monkeypatch.setattr("cart.services.B2BClient", FakeB2BClient)


@pytest.mark.django_db
def test_add_sku_increments_quantity_if_already_in_cart(client, monkeypatch):
    product_id = uuid.uuid4()
    sku_id = uuid.uuid4()
    _install_fake_b2b(monkeypatch, product_id=product_id, sku_id=sku_id)

    session_id = uuid.uuid4()
    client.defaults["HTTP_X_SESSION_ID"] = str(session_id)

    body = {"sku_id": str(sku_id), "quantity": 2}
    r1 = client.post("/api/v1/cart/items", data=json.dumps(body), content_type="application/json")
    r2 = client.post("/api/v1/cart/items", data=json.dumps(body), content_type="application/json")

    assert r1.status_code == 200
    assert r2.status_code == 200
    assert CartItem.objects.get(sku_id=sku_id).quantity == 4


@pytest.mark.django_db
def test_get_cart_enriched_with_b2b_data(client, monkeypatch):
    product_id = uuid.uuid4()
    sku_id = uuid.uuid4()
    _install_fake_b2b(
        monkeypatch,
        product_id=product_id,
        sku_id=sku_id,
        title="Galaxy",
        price=25000,
    )

    session_id = uuid.uuid4()
    client.defaults["HTTP_X_SESSION_ID"] = str(session_id)
    client.post(
        "/api/v1/cart/items",
        data=json.dumps({"sku_id": str(sku_id), "quantity": 1}),
        content_type="application/json",
    )

    r = client.get("/api/v1/cart")
    assert r.status_code == 200
    data = r.json()
    assert len(data["items"]) == 1
    item = data["items"][0]
    assert item["sku_id"] == str(sku_id)
    assert item["product_id"] == str(product_id)
    assert "Galaxy" in item["name"]
    assert item["unit_price"] == 25000
    assert item["line_total"] == 25000
    assert data["subtotal"] == 25000


@pytest.mark.django_db
def test_unavailable_sku_shown_with_reason(client, monkeypatch):
    product_id = uuid.uuid4()
    sku_id = uuid.uuid4()
    _install_fake_b2b(
        monkeypatch,
        product_id=product_id,
        sku_id=sku_id,
        active_quantity=0,
    )

    session_id = uuid.uuid4()
    client.defaults["HTTP_X_SESSION_ID"] = str(session_id)

    cart = Cart.objects.create(session_id=session_id, user=None)
    CartItem.objects.create(
        cart=cart,
        sku_id=sku_id,
        product_id=product_id,
        quantity=1,
        unit_price_at_add=1000,
    )

    r = client.get("/api/v1/cart")
    assert r.status_code == 200
    item = r.json()["items"][0]
    assert item["is_available"] is False
    assert r.json()["is_valid"] is False


@pytest.mark.django_db
def test_guest_cart_merged_on_login(client, monkeypatch):
    product_id = uuid.uuid4()
    sku_id = uuid.uuid4()
    _install_fake_b2b(monkeypatch, product_id=product_id, sku_id=sku_id, active_quantity=10)

    guest_session = uuid.uuid4()
    client.defaults["HTTP_X_SESSION_ID"] = str(guest_session)
    client.post(
        "/api/v1/cart/items",
        data=json.dumps({"sku_id": str(sku_id), "quantity": 3}),
        content_type="application/json",
    )

    user = User.objects.create_user(
        email="cart@example.com",
        password="secret",
        first_name="C",
        last_name="U",
    )
    user_cart = Cart.objects.create(user=user, session_id=None)
    CartItem.objects.create(
        cart=user_cart,
        sku_id=sku_id,
        product_id=product_id,
        quantity=2,
        unit_price_at_add=19900,
    )

    login = client.post(
        "/api/v1/auth/login",
        data=json.dumps({"email": "cart@example.com", "password": "secret"}),
        content_type="application/json",
        HTTP_X_SESSION_ID=str(guest_session),
    )
    assert login.status_code == 200
    token_body = login.json()
    assert set(token_body.keys()) == {
        "access_token",
        "refresh_token",
        "token_type",
        "expires_in",
        "user_id",
    }
    assert token_body["user_id"] == str(user.id)
    assert token_body["token_type"] == "Bearer"

    merged_item = CartItem.objects.get(cart__user=user, sku_id=sku_id)
    assert merged_item.quantity == 3
    assert not Cart.objects.filter(session_id=guest_session).exists()


@pytest.mark.django_db
def test_cart_validate_returns_issues(client, monkeypatch):
    product_id = uuid.uuid4()
    sku_id = uuid.uuid4()
    _install_fake_b2b(
        monkeypatch,
        product_id=product_id,
        sku_id=sku_id,
        price=15000,
        active_quantity=0,
    )

    session_id = uuid.uuid4()
    client.defaults["HTTP_X_SESSION_ID"] = str(session_id)
    cart = Cart.objects.create(session_id=session_id, user=None)
    CartItem.objects.create(
        cart=cart,
        sku_id=sku_id,
        product_id=product_id,
        quantity=2,
        unit_price_at_add=10000,
    )

    r = client.post("/api/v1/cart/validate")
    assert r.status_code == 200
    body = r.json()
    assert body["is_valid"] is False
    assert body["cart"]["is_valid"] is False
    issue_types = {issue["type"] for issue in body["issues"]}
    assert "OUT_OF_STOCK" in issue_types
    assert "PRICE_CHANGED" in issue_types
