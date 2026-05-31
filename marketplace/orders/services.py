"""Checkout и отмена заказов (OpenAPI Orders)."""

from __future__ import annotations

import logging
import uuid
from datetime import timedelta
from uuid import UUID

from django.db import transaction
from django.utils import timezone

from cart.services import get_or_create_user_cart, validate_cart
from catalog.b2b_client import B2BClient, B2BClientError

from .models import Address, Order, OrderItem, PaymentMethod, hash_checkout_request

logger = logging.getLogger(__name__)

IDEMPOTENCY_TTL = timedelta(hours=1)
CANCELLABLE_STATUSES = frozenset({Order.Status.CREATED, Order.Status.PAID})


class CheckoutError(Exception):
    def __init__(self, *, code: str, message: str, details=None, status_code: int = 400):
        self.code = code
        self.message = message
        self.details = details
        self.status_code = status_code
        super().__init__(message)


class CancelError(Exception):
    def __init__(self, *, code: str, message: str, details=None, status_code: int = 400):
        self.code = code
        self.message = message
        self.details = details
        self.status_code = status_code
        super().__init__(message)


def _order_number(order_id: UUID) -> str:
    year = timezone.now().year
    suffix = str(order_id).replace("-", "")[:6].upper()
    return f"NM-{year}-{suffix}"


def _iso_z(dt) -> str:
    return dt.isoformat().replace("+00:00", "Z")


def _append_status_history(order: Order, *, status: str, reason: str | None = None) -> None:
    history = list(order.status_history or [])
    history.append(
        {
            "status": status,
            "changed_at": _iso_z(timezone.now()),
            "reason": reason,
        }
    )
    order.status_history = history


def _address_snapshot(address: Address) -> dict:
    return {
        "id": str(address.id),
        "country": address.country,
        "region": address.region,
        "city": address.city,
        "street": address.street,
        "building": address.building,
        "apartment": address.apartment,
        "postal_code": address.postal_code,
        "recipient_name": address.recipient_name,
        "recipient_phone": address.recipient_phone,
        "is_default": address.is_default,
        "comment": address.comment,
        "created_at": address.created_at.isoformat().replace("+00:00", "Z"),
    }


def _payment_method_snapshot(method: PaymentMethod) -> dict:
    return {
        "id": str(method.id),
        "type": method.type,
        "card_last4": method.card_last4 or None,
        "card_brand": method.card_brand or None,
        "is_default": method.is_default,
        "created_at": method.created_at.isoformat().replace("+00:00", "Z"),
    }


def _split_line_name(name: str) -> tuple[str, str]:
    if " — " in name:
        product_title, sku_name = name.split(" — ", 1)
        return product_title.strip(), sku_name.strip()
    return name.strip(), ""


def _find_idempotent_order(*, buyer, idempotency_key: UUID) -> Order | None:
    cutoff = timezone.now() - IDEMPOTENCY_TTL
    return (
        Order.objects.filter(
            buyer=buyer,
            idempotency_key=idempotency_key,
            created_at__gte=cutoff,
        )
        .prefetch_related("items")
        .first()
    )


def _build_reserve_items(cart_lines: list[dict]) -> list[dict]:
    return [
        {"sku_id": line["sku_id"], "quantity": int(line["quantity"])}
        for line in cart_lines
        if line.get("is_available")
    ]


def _failed_items_from_b2b(exc: B2BClientError) -> list[dict]:
    details = (exc.body or {}).get("details") or {}
    skus = details.get("skus") or []
    failed: list[dict] = []
    for row in skus:
        if not isinstance(row, dict):
            continue
        failed.append(
            {
                "sku_id": row.get("sku_id"),
                "reason": row.get("reason", "insufficient_stock"),
                "requested": row.get("requested"),
                "available": row.get("available"),
            }
        )
    return failed


def checkout_order(
    *,
    buyer,
    idempotency_key: UUID,
    body: dict,
) -> tuple[Order, bool]:
    """Возвращает (order, created). created=False — идемпотентный повтор."""
    request_hash = hash_checkout_request(body)

    existing = _find_idempotent_order(buyer=buyer, idempotency_key=idempotency_key)
    if existing is not None:
        if existing.request_hash != request_hash:
            raise CheckoutError(
                code="CONFLICT",
                message="Idempotency-Key already used with a different request body",
                status_code=409,
            )
        return existing, False

    address_id = body["address_id"]
    payment_method_id = body["payment_method_id"]

    try:
        address = Address.objects.get(id=address_id, user=buyer)
    except Address.DoesNotExist as exc:
        raise CheckoutError(
            code="NOT_FOUND",
            message="Address not found",
            status_code=404,
        ) from exc

    try:
        payment_method = PaymentMethod.objects.get(id=payment_method_id, user=buyer)
    except PaymentMethod.DoesNotExist as exc:
        raise CheckoutError(
            code="NOT_FOUND",
            message="Payment method not found",
            status_code=404,
        ) from exc

    cart = get_or_create_user_cart(buyer)
    validation = validate_cart(cart)
    if not validation["is_valid"]:
        raise CheckoutError(
            code="CART_INVALID",
            message="Cart validation failed",
            details={"validation": validation},
            status_code=422,
        )

    cart_lines = validation["cart"]["items"]
    if not cart_lines:
        raise CheckoutError(
            code="VALIDATION_ERROR",
            message="Cart is empty",
            status_code=400,
        )

    items_snapshot = body.get("items_snapshot")
    if items_snapshot:
        _assert_items_snapshot_matches(cart_lines, items_snapshot)

    reserve_items = _build_reserve_items(cart_lines)
    order_id = uuid.uuid4()
    client = B2BClient()

    try:
        client.reserve_inventory(
            idempotency_key=idempotency_key,
            order_id=order_id,
            items=reserve_items,
        )
    except B2BClientError as exc:
        if exc.status_code in (502, 503):
            raise CheckoutError(
                code="SERVICE_UNAVAILABLE",
                message="B2B inventory service unavailable",
                status_code=503,
            ) from exc
        if exc.status_code == 409:
            failed = _failed_items_from_b2b(exc)
            raise CheckoutError(
                code="RESERVE_FAILED",
                message=exc.message or "Failed to reserve inventory",
                details={"failed_items": failed},
                status_code=409,
            ) from exc
        raise CheckoutError(
            code="ERROR",
            message=exc.message or "B2B error",
            status_code=502,
        ) from exc

    now = timezone.now()
    subtotal = sum(int(line["line_total"]) for line in cart_lines if line.get("is_available"))
    delivery_cost = 0
    total = subtotal + delivery_cost

    with transaction.atomic():
        duplicate = _find_idempotent_order(buyer=buyer, idempotency_key=idempotency_key)
        if duplicate is not None:
            if duplicate.request_hash != request_hash:
                raise CheckoutError(
                    code="CONFLICT",
                    message="Idempotency-Key already used with a different request body",
                    status_code=409,
                )
            return duplicate, False

        paid_history = [
            {
                "status": Order.Status.PAID,
                "changed_at": _iso_z(now),
                "reason": None,
            }
        ]
        order = Order.objects.create(
            id=order_id,
            buyer=buyer,
            number=_order_number(order_id),
            status=Order.Status.PAID,
            status_history=paid_history,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
            address_snapshot=_address_snapshot(address),
            payment_method_snapshot=_payment_method_snapshot(payment_method),
            subtotal=subtotal,
            delivery_cost=delivery_cost,
            total=total,
            comment=body.get("comment") or "",
            paid_at=now,
        )

        for line in cart_lines:
            if not line.get("is_available"):
                continue
            product_title, sku_name = _split_line_name(line.get("name") or "")
            unit_price = int(line["unit_price"])
            quantity = int(line["quantity"])
            image_url = ""
            image = line.get("image")
            if isinstance(image, dict) and image.get("url"):
                image_url = str(image["url"])

            OrderItem.objects.create(
                order=order,
                sku_id=UUID(str(line["sku_id"])),
                product_id=UUID(str(line["product_id"])),
                product_title=product_title,
                sku_name=sku_name,
                sku_code=str(line.get("sku_code") or ""),
                quantity=quantity,
                unit_price=unit_price,
                line_total=unit_price * quantity,
                image_url=image_url,
            )

    return order, True


def _assert_items_snapshot_matches(cart_lines: list[dict], snapshot: list) -> None:
    cart_map = {
        str(line["sku_id"]): line
        for line in cart_lines
        if line.get("is_available")
    }
    for row in snapshot:
        sku_id = str(row["sku_id"])
        if sku_id not in cart_map:
            raise CheckoutError(
                code="CART_INVALID",
                message="items_snapshot does not match cart",
                status_code=422,
            )
        cart_line = cart_map[sku_id]
        if int(row["quantity"]) != int(cart_line["quantity"]):
            raise CheckoutError(
                code="CART_INVALID",
                message="items_snapshot quantity mismatch",
                status_code=422,
            )
        if int(row["unit_price"]) != int(cart_line["unit_price"]):
            raise CheckoutError(
                code="CART_INVALID",
                message="items_snapshot price mismatch",
                status_code=422,
            )


def _build_unreserve_items(order: Order) -> list[dict]:
    return [
        {"sku_id": row.sku_id, "quantity": row.quantity}
        for row in order.items.all()
    ]


def _call_b2b_unreserve(order: Order) -> bool:
    """Возвращает True, если unreserve успешен (или резерва уже не было)."""
    client = B2BClient()
    items = _build_unreserve_items(order)
    try:
        client.unreserve_inventory(order_id=order.id, items=items)
        return True
    except B2BClientError as exc:
        if exc.status_code == 404:
            return True
        logger.error(
            "B2B unreserve failed for order %s: %s (status=%s)",
            order.id,
            exc.message,
            exc.status_code,
            exc_info=True,
        )
        return False


def _finalize_cancelled(order_id: UUID, *, cancel_reason: str) -> Order:
    with transaction.atomic():
        order = Order.objects.select_for_update().prefetch_related("items").get(pk=order_id)
        order.status = Order.Status.CANCELLED
        order.cancel_reason = cancel_reason
        _append_status_history(order, status=Order.Status.CANCELLED, reason=cancel_reason or None)
        order.save(update_fields=["status", "cancel_reason", "status_history"])
    return order


def cancel_order(*, buyer, order_id: UUID, reason: str = "") -> Order:
    """
    OpenAPI POST /orders/{order_id}/cancel:
    CANCEL_PENDING → unreserve B2B → CANCELLED или остаётся CANCEL_PENDING.
    """
    cancel_reason = (reason or "").strip()[:500]

    try:
        order = Order.objects.prefetch_related("items").get(id=order_id, buyer=buyer)
    except Order.DoesNotExist as exc:
        raise CancelError(
            code="NOT_FOUND",
            message="Order not found",
            status_code=404,
        ) from exc

    if order.status == Order.Status.CANCELLED:
        return order

    if order.status == Order.Status.CANCEL_PENDING:
        if _call_b2b_unreserve(order):
            return _finalize_cancelled(order.id, cancel_reason=order.cancel_reason or cancel_reason)
        return Order.objects.prefetch_related("items").get(pk=order.pk)

    if order.status not in CANCELLABLE_STATUSES:
        raise CancelError(
            code="CANCEL_NOT_ALLOWED",
            message="Order cannot be cancelled in the current status",
            details={"status": order.status},
            status_code=409,
        )

    with transaction.atomic():
        order = Order.objects.select_for_update().prefetch_related("items").get(pk=order.pk)
        order.status = Order.Status.CANCEL_PENDING
        order.cancel_reason = cancel_reason
        _append_status_history(
            order,
            status=Order.Status.CANCEL_PENDING,
            reason=cancel_reason or None,
        )
        order.save(update_fields=["status", "cancel_reason", "status_history"])

    if _call_b2b_unreserve(order):
        return _finalize_cancelled(order.id, cancel_reason=cancel_reason)

    return Order.objects.prefetch_related("items").get(pk=order.pk)


def retry_cancel_unreserve_for_pending_orders() -> int:
    """Management command / cron: повтор unreserve для CANCEL_PENDING."""
    processed = 0
    pending_ids = Order.objects.filter(status=Order.Status.CANCEL_PENDING).values_list("id", flat=True)
    for order_id in pending_ids:
        order = Order.objects.prefetch_related("items").get(pk=order_id)
        if _call_b2b_unreserve(order):
            _finalize_cancelled(order.id, cancel_reason=order.cancel_reason)
            processed += 1
    return processed
