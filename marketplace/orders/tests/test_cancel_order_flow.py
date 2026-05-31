"""Канон b2c-11-cancel-order: POST /api/v1/orders/{id}/cancel."""

import uuid

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from catalog.b2b_client import B2BClientError
from orders.models import Address, Order, OrderItem, PaymentMethod

User = get_user_model()


@pytest.fixture
def buyer(db):
    return User.objects.create_user(
        email="buyer-cancel@example.com",
        password="password12345",
        first_name="Buyer",
        last_name="Cancel",
    )


@pytest.fixture
def other_buyer(db):
    return User.objects.create_user(
        email="other-cancel@example.com",
        password="password12345",
        first_name="Other",
        last_name="User",
    )


@pytest.fixture
def auth_client(buyer):
    client = APIClient()
    client.force_authenticate(user=buyer)
    return client


def _create_paid_order(buyer):
    address = Address.objects.create(
        user=buyer,
        country="RU",
        city="Moscow",
        street="Lenina",
        building="10",
    )
    payment = PaymentMethod.objects.create(
        user=buyer,
        type=PaymentMethod.Type.CARD,
        card_last4="1111",
        card_brand="VISA",
    )
    order_id = uuid.uuid4()
    order = Order.objects.create(
        id=order_id,
        buyer=buyer,
        number=f"NM-2026-{str(order_id)[:6].upper()}",
        status=Order.Status.PAID,
        idempotency_key=uuid.uuid4(),
        request_hash="test",
        address_snapshot={"id": str(address.id), "city": "Moscow"},
        payment_method_snapshot={"id": str(payment.id), "type": "CARD"},
        subtotal=100_000,
        delivery_cost=0,
        total=100_000,
    )
    OrderItem.objects.create(
        order=order,
        sku_id=uuid.uuid4(),
        product_id=uuid.uuid4(),
        product_title="Phone",
        sku_name="128GB",
        quantity=2,
        unit_price=50_000,
        line_total=100_000,
    )
    return order


def _install_unreserve(monkeypatch, *, side_effect=None):
    calls = {"count": 0}

    def unreserve_inventory(self, **kwargs):
        calls["count"] += 1
        calls["last"] = kwargs
        if side_effect:
            raise side_effect
        return {
            "order_id": str(kwargs["order_id"]),
            "status": "UNRESERVED",
            "processed_at": "2026-05-31T12:00:00.000Z",
        }

    monkeypatch.setattr(
        "orders.services.B2BClient.unreserve_inventory",
        unreserve_inventory,
    )
    return calls


@pytest.mark.django_db
def test_cancel_paid_order_transitions_to_cancelled(auth_client, buyer, monkeypatch):
    order = _create_paid_order(buyer)
    calls = _install_unreserve(monkeypatch)

    response = auth_client.post(
        f"/api/v1/orders/{order.id}/cancel",
        {"reason": "Changed my mind"},
        format="json",
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "CANCELLED"
    assert data["cancel_reason"] == "Changed my mind"
    assert calls["count"] == 1
    assert calls["last"]["order_id"] == order.id

    order.refresh_from_db()
    assert order.status == Order.Status.CANCELLED


@pytest.mark.django_db
def test_unreserve_failure_transitions_to_cancel_pending(auth_client, buyer, monkeypatch):
    order = _create_paid_order(buyer)
    _install_unreserve(
        monkeypatch,
        side_effect=B2BClientError(503, "B2B unavailable"),
    )

    response = auth_client.post(
        f"/api/v1/orders/{order.id}/cancel",
        format="json",
    )

    assert response.status_code == 200
    assert response.json()["status"] == "CANCEL_PENDING"

    order.refresh_from_db()
    assert order.status == Order.Status.CANCEL_PENDING


@pytest.mark.django_db
def test_cancel_assembling_order_transitions_to_cancelled(auth_client, buyer, monkeypatch):
    order = _create_paid_order(buyer)
    order.status = Order.Status.ASSEMBLING
    order.save(update_fields=["status"])
    _install_unreserve(monkeypatch)

    response = auth_client.post(
        f"/api/v1/orders/{order.id}/cancel",
        format="json",
    )

    assert response.status_code == 200
    assert response.json()["status"] == "CANCELLED"

    order.refresh_from_db()
    assert order.status == Order.Status.CANCELLED


@pytest.mark.django_db
def test_cancel_delivering_order_returns_409(auth_client, buyer, monkeypatch):
    order = _create_paid_order(buyer)
    order.status = Order.Status.DELIVERING
    order.save(update_fields=["status"])
    _install_unreserve(monkeypatch)

    response = auth_client.post(
        f"/api/v1/orders/{order.id}/cancel",
        format="json",
    )

    assert response.status_code == 409
    body = response.json()
    assert body["code"] == "CANCEL_NOT_ALLOWED"
    assert body["details"]["status"] == "DELIVERING"

    order.refresh_from_db()
    assert order.status == Order.Status.DELIVERING


@pytest.mark.django_db
def test_other_user_order_returns_404(other_buyer, buyer, monkeypatch):
    order = _create_paid_order(buyer)
    _install_unreserve(monkeypatch)

    client = APIClient()
    client.force_authenticate(user=other_buyer)

    response = client.post(
        f"/api/v1/orders/{order.id}/cancel",
        format="json",
    )

    assert response.status_code == 404
    assert response.json()["code"] == "NOT_FOUND"

    order.refresh_from_db()
    assert order.status == Order.Status.PAID
