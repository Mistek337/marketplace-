"""Канон b2c-9-checkout: POST /api/v1/orders."""

import uuid

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from cart.models import Cart, CartItem
from catalog.b2b_client import B2BClientError
from orders.models import Address, Order, OrderItem, PaymentMethod

User = get_user_model()


def _product(product_id, sku_id, *, price=50_000, active_quantity=5, title="Phone"):
    return {
        "id": str(product_id),
        "title": title,
        "slug": "phone",
        "description": "d",
        "status": "MODERATED",
        "deleted": False,
        "category_id": str(uuid.uuid4()),
        "images": [{"id": str(uuid.uuid4()), "url": "https://cdn/p.jpg", "ordering": 0}],
        "skus": [
            {
                "id": str(sku_id),
                "name": "128GB",
                "article": "SKU-1",
                "price": price,
                "active_quantity": active_quantity,
                "stock_quantity": active_quantity,
            }
        ],
    }


@pytest.fixture
def buyer(db):
    return User.objects.create_user(
        email="buyer-checkout@example.com",
        password="password12345",
        first_name="Buyer",
        last_name="Test",
    )


@pytest.fixture
def auth_client(buyer):
    client = APIClient()
    client.force_authenticate(user=buyer)
    return client


@pytest.fixture
def checkout_setup(buyer):
    product_id = uuid.uuid4()
    sku_id = uuid.uuid4()
    address = Address.objects.create(
        user=buyer,
        country="RU",
        city="Moscow",
        street="Tverskaya",
        building="1",
    )
    payment = PaymentMethod.objects.create(
        user=buyer,
        type=PaymentMethod.Type.CARD,
        card_last4="4242",
        card_brand="VISA",
    )
    cart = Cart.objects.create(user=buyer)
    CartItem.objects.create(
        cart=cart,
        sku_id=sku_id,
        product_id=product_id,
        quantity=2,
        unit_price_at_add=50_000,
    )
    return {
        "product_id": product_id,
        "sku_id": sku_id,
        "address_id": address.id,
        "payment_method_id": payment.id,
        "product": _product(product_id, sku_id),
    }


def _install_b2b(monkeypatch, product, *, reserve_side_effect=None):
    metrics = {"reserve_calls": 0}

    class FakeB2B:
        def batch_public_products(self, product_ids):
            return [product]

        def get_public_sku(self, sku_id):
            sku = product["skus"][0]
            return {
                "id": sku["id"],
                "product_id": product["id"],
                "name": sku["name"],
                "price": sku["price"],
                "active_quantity": sku["active_quantity"],
            }

        def get_product(self, product_id):
            return product

        def reserve_inventory(self, **kwargs):
            metrics["reserve_calls"] += 1
            if reserve_side_effect:
                raise reserve_side_effect
            return {
                "order_id": kwargs["order_id"],
                "status": "RESERVED",
                "reserved_at": "2026-05-20T12:00:00.000Z",
            }

    fake = FakeB2B()
    fake.metrics = metrics
    monkeypatch.setattr("cart.services.B2BClient", lambda: fake)
    monkeypatch.setattr("orders.services.B2BClient", lambda: fake)
    return fake


@pytest.mark.django_db
def test_checkout_creates_paid_order_with_fixed_prices(auth_client, checkout_setup, monkeypatch):
    setup = checkout_setup
    idempotency_key = uuid.uuid4()
    _install_b2b(monkeypatch, setup["product"])

    response = auth_client.post(
        "/api/v1/orders",
        {
            "address_id": str(setup["address_id"]),
            "payment_method_id": str(setup["payment_method_id"]),
        },
        format="json",
        HTTP_IDEMPOTENCY_KEY=str(idempotency_key),
    )

    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "PAID"
    assert data["subtotal"] == 100_000
    assert len(data["items"]) == 1
    assert data["items"][0]["unit_price"] == 50_000
    assert data["items"][0]["quantity"] == 2

    order = Order.objects.get(id=data["id"])
    item = OrderItem.objects.get(order=order)
    assert item.unit_price == 50_000
    assert item.product_title == "Phone"
    assert item.sku_name == "128GB"
    assert order.paid_at is not None


@pytest.mark.django_db
def test_partial_reserve_failure_returns_409(auth_client, checkout_setup, monkeypatch):
    setup = checkout_setup
    conflict = B2BClientError(
        409,
        "Cannot reserve",
        body={
            "code": "CONFLICT",
            "message": "Cannot reserve",
            "details": {
                "skus": [
                    {
                        "sku_id": str(setup["sku_id"]),
                        "reason": "insufficient_stock",
                        "requested": 2,
                        "available": 0,
                    }
                ]
            },
        },
    )
    _install_b2b(monkeypatch, setup["product"], reserve_side_effect=conflict)

    response = auth_client.post(
        "/api/v1/orders",
        {
            "address_id": str(setup["address_id"]),
            "payment_method_id": str(setup["payment_method_id"]),
        },
        format="json",
        HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()),
    )

    assert response.status_code == 409
    body = response.json()
    assert body["code"] == "RESERVE_FAILED"
    assert body["details"]["failed_items"][0]["sku_id"] == str(setup["sku_id"])
    assert Order.objects.count() == 0


@pytest.mark.django_db
def test_idempotent_returns_existing_order(auth_client, checkout_setup, monkeypatch):
    setup = checkout_setup
    idempotency_key = uuid.uuid4()
    fake = _install_b2b(monkeypatch, setup["product"])

    payload = {
        "address_id": str(setup["address_id"]),
        "payment_method_id": str(setup["payment_method_id"]),
    }
    first = auth_client.post(
        "/api/v1/orders",
        payload,
        format="json",
        HTTP_IDEMPOTENCY_KEY=str(idempotency_key),
    )
    second = auth_client.post(
        "/api/v1/orders",
        payload,
        format="json",
        HTTP_IDEMPOTENCY_KEY=str(idempotency_key),
    )

    assert first.status_code == 201
    assert second.status_code == 200
    assert first.json()["id"] == second.json()["id"]
    assert Order.objects.count() == 1
    assert fake.metrics["reserve_calls"] == 1


@pytest.mark.django_db
def test_b2b_unavailable_returns_503(auth_client, checkout_setup, monkeypatch):
    setup = checkout_setup
    _install_b2b(
        monkeypatch,
        setup["product"],
        reserve_side_effect=B2BClientError(503, "B2B unavailable"),
    )

    response = auth_client.post(
        "/api/v1/orders",
        {
            "address_id": str(setup["address_id"]),
            "payment_method_id": str(setup["payment_method_id"]),
        },
        format="json",
        HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()),
    )

    assert response.status_code == 503
    assert response.json()["code"] == "SERVICE_UNAVAILABLE"
    assert Order.objects.count() == 0
