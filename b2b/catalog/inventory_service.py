"""Резервирование SKU: all-or-nothing, SELECT FOR UPDATE, идемпотентность (OpenAPI Inventory)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta, timezone as dt_timezone
from typing import Any
from uuid import UUID

from django.db import transaction
from django.db.models import F
from django.utils import timezone as django_tz

from .api_errors import CONFLICT, NOT_FOUND, error_body
from .b2c_client import emit_sku_out_of_stock_event
from .models import InventoryReservation, Product, SKU

RESERVE_IDEMPOTENCY_TTL = timedelta(hours=1)


@dataclass(frozen=True)
class InventoryItemInput:
    sku_id: UUID
    quantity: int


class InventoryConflict(Exception):
    def __init__(self, *, message: str, details: dict[str, Any]) -> None:
        super().__init__(message)
        self.message = message
        self.details = details


class InventoryNotFound(Exception):
    def __init__(self, *, message: str) -> None:
        super().__init__(message)
        self.message = message


def _iso_z(dt) -> str:
    return dt.astimezone(dt_timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _aggregate_items(items: list[InventoryItemInput]) -> list[InventoryItemInput]:
    merged: dict[UUID, int] = {}
    for row in items:
        merged[row.sku_id] = merged.get(row.sku_id, 0) + row.quantity
    return [InventoryItemInput(sku_id=sku_id, quantity=qty) for sku_id, qty in merged.items()]


def _reserve_response(*, order_id: UUID, reserved_at) -> dict[str, Any]:
    return {
        "order_id": str(order_id),
        "status": "RESERVED",
        "reserved_at": _iso_z(reserved_at),
    }


def _unreserve_response(*, order_id: UUID, processed_at) -> dict[str, Any]:
    return {
        "order_id": str(order_id),
        "status": "UNRESERVED",
        "processed_at": _iso_z(processed_at),
    }


def _fulfill_response(*, order_id: UUID, processed_at) -> dict[str, Any]:
    return {
        "order_id": str(order_id),
        "status": "FULFILLED",
        "processed_at": _iso_z(processed_at),
    }


def _find_active_reservation_by_idempotency(idempotency_key: UUID) -> InventoryReservation | None:
    cutoff = django_tz.now() - RESERVE_IDEMPOTENCY_TTL
    return (
        InventoryReservation.objects.filter(
            idempotency_key=idempotency_key,
            created_at__gte=cutoff,
        )
        .first()
    )


def _validate_reservable_product(product: Product) -> str | None:
    if product.deleted:
        return "product_deleted"
    if product.status != Product.Status.MODERATED:
        return "product_not_available"
    return None


def reserve_inventory(
    *,
    idempotency_key: UUID,
    order_id: UUID,
    items: list[InventoryItemInput],
) -> tuple[dict[str, Any], list[UUID]]:
    """
  Возвращает (response_body, sku_ids_to_notify_out_of_stock).
  sku_ids — только при новом успешном reserve (не при идемпотентном повторе).
    """
    aggregated = _aggregate_items(items)
    if not aggregated:
        raise InventoryConflict(
            message="Reservation items are required",
            details={"items": "At least one item is required"},
        )

    existing = _find_active_reservation_by_idempotency(idempotency_key)
    if existing is not None:
        return existing.response_payload, []

    out_of_stock_after: list[UUID] = []
    reserved_at = django_tz.now()

    with transaction.atomic():
        prior = _find_active_reservation_by_idempotency(idempotency_key)
        if prior is not None:
            return prior.response_payload, []

        if InventoryReservation.objects.filter(order_id=order_id).exists():
            raise InventoryConflict(
                message="Order already has a reservation",
                details={"order_id": str(order_id)},
            )

        sku_ids = sorted({row.sku_id for row in aggregated}, key=str)
        skus = list(
            SKU.objects.select_for_update()
            .filter(id__in=sku_ids)
            .select_related("product")
        )
        skus_by_id = {sku.id: sku for sku in skus}

        problems: list[dict[str, Any]] = []
        for row in aggregated:
            sku = skus_by_id.get(row.sku_id)
            if sku is None:
                problems.append(
                    {
                        "sku_id": str(row.sku_id),
                        "reason": "sku_not_found",
                    }
                )
                continue

            product_reason = _validate_reservable_product(sku.product)
            if product_reason:
                problems.append(
                    {
                        "sku_id": str(row.sku_id),
                        "reason": product_reason,
                    }
                )
                continue

            if sku.active_quantity < row.quantity:
                problems.append(
                    {
                        "sku_id": str(row.sku_id),
                        "reason": "insufficient_stock",
                        "requested": row.quantity,
                        "available": sku.active_quantity,
                    }
                )

        if problems:
            raise InventoryConflict(
                message="Cannot reserve inventory for one or more SKUs",
                details={"skus": problems},
            )

        for row in aggregated:
            sku = skus_by_id[row.sku_id]
            updated = SKU.objects.filter(pk=sku.pk, active_quantity__gte=row.quantity).update(
                active_quantity=F("active_quantity") - row.quantity,
                reserved_quantity=F("reserved_quantity") + row.quantity,
                updated_at=django_tz.now(),
            )
            if updated != 1:
                raise InventoryConflict(
                    message="Cannot reserve inventory for one or more SKUs",
                    details={
                        "skus": [
                            {
                                "sku_id": str(row.sku_id),
                                "reason": "insufficient_stock",
                                "requested": row.quantity,
                            }
                        ]
                    },
                )

        for row in aggregated:
            sku = skus_by_id[row.sku_id]
            sku.refresh_from_db(fields=["active_quantity"])
            if sku.active_quantity == 0:
                out_of_stock_after.append(sku.id)

        payload_items = [{"sku_id": str(r.sku_id), "quantity": r.quantity} for r in aggregated]
        response = _reserve_response(order_id=order_id, reserved_at=reserved_at)
        InventoryReservation.objects.create(
            idempotency_key=idempotency_key,
            order_id=order_id,
            items=payload_items,
            response_payload=response,
            reserved_at=reserved_at,
        )

    return response, out_of_stock_after


def unreserve_inventory(*, order_id: UUID) -> dict[str, Any]:
    processed_at = django_tz.now()

    with transaction.atomic():
        reservation = (
            InventoryReservation.objects.select_for_update()
            .filter(order_id=order_id)
            .first()
        )
        if reservation is None:
            raise InventoryNotFound(message="Reservation for order not found")

        if reservation.unreserved_at is not None:
            return _unreserve_response(order_id=order_id, processed_at=reservation.unreserved_at)

        items = [
            InventoryItemInput(sku_id=UUID(row["sku_id"]), quantity=int(row["quantity"]))
            for row in reservation.items
        ]
        sku_ids = sorted({row.sku_id for row in items}, key=str)
        skus = list(SKU.objects.select_for_update().filter(id__in=sku_ids))
        skus_by_id = {sku.id: sku for sku in skus}

        for row in items:
            sku = skus_by_id.get(row.sku_id)
            if sku is None:
                raise InventoryNotFound(message=f"SKU {row.sku_id} not found for unreserve")
            if sku.reserved_quantity < row.quantity:
                raise InventoryConflict(
                    message="Reserved quantity is lower than requested unreserve",
                    details={
                        "sku_id": str(row.sku_id),
                        "requested": row.quantity,
                        "reserved": sku.reserved_quantity,
                    },
                )

        for row in items:
            sku = skus_by_id[row.sku_id]
            SKU.objects.filter(pk=sku.pk).update(
                active_quantity=F("active_quantity") + row.quantity,
                reserved_quantity=F("reserved_quantity") - row.quantity,
                updated_at=django_tz.now(),
            )

        reservation.unreserved_at = processed_at
        reservation.save(update_fields=["unreserved_at"])

    return _unreserve_response(order_id=order_id, processed_at=processed_at)


def fulfill_inventory(*, order_id: UUID, items: list[InventoryItemInput]) -> dict[str, Any]:
    """
    Списание резерва при доставке (OpenAPI fulfillInventory).
    active_quantity не меняется; reserved_quantity уменьшается.
    Идемпотентно по order_id через InventoryReservation.fulfilled_at.
    """
    aggregated = _aggregate_items(items)
    if not aggregated:
        raise InventoryConflict(
            message="Fulfill items are required",
            details={"items": "At least one item is required"},
        )

    processed_at = django_tz.now()

    with transaction.atomic():
        reservation = (
            InventoryReservation.objects.select_for_update()
            .filter(order_id=order_id)
            .first()
        )
        if reservation is None:
            raise InventoryNotFound(message="Reservation for order not found")

        if reservation.unreserved_at is not None:
            raise InventoryConflict(
                message="Order reservation was already unreserved",
                details={"order_id": str(order_id)},
            )

        if reservation.fulfilled_at is not None:
            return _fulfill_response(order_id=order_id, processed_at=reservation.fulfilled_at)

        reserved_items = [
            InventoryItemInput(sku_id=UUID(row["sku_id"]), quantity=int(row["quantity"]))
            for row in reservation.items
        ]
        reserved_by_sku = {row.sku_id: row.quantity for row in _aggregate_items(reserved_items)}
        for row in aggregated:
            expected = reserved_by_sku.get(row.sku_id)
            if expected is None or expected != row.quantity:
                raise InventoryConflict(
                    message="Fulfill items do not match reservation",
                    details={
                        "sku_id": str(row.sku_id),
                        "expected": expected,
                        "requested": row.quantity,
                    },
                )

        sku_ids = sorted({row.sku_id for row in aggregated}, key=str)
        skus = list(SKU.objects.select_for_update().filter(id__in=sku_ids))
        skus_by_id = {sku.id: sku for sku in skus}

        for row in aggregated:
            sku = skus_by_id.get(row.sku_id)
            if sku is None:
                raise InventoryNotFound(message=f"SKU {row.sku_id} not found for fulfill")
            if sku.reserved_quantity < row.quantity:
                raise InventoryConflict(
                    message="Reserved quantity is lower than requested fulfill",
                    details={
                        "sku_id": str(row.sku_id),
                        "requested": row.quantity,
                        "reserved": sku.reserved_quantity,
                    },
                )

        for row in aggregated:
            sku = skus_by_id[row.sku_id]
            SKU.objects.filter(pk=sku.pk).update(
                reserved_quantity=F("reserved_quantity") - row.quantity,
                updated_at=django_tz.now(),
            )

        reservation.fulfilled_at = processed_at
        reservation.save(update_fields=["fulfilled_at"])

    return _fulfill_response(order_id=order_id, processed_at=processed_at)


def conflict_error_response(exc: InventoryConflict):
    from rest_framework import status
    from rest_framework.response import Response

    return Response(
        error_body(code=CONFLICT, message=exc.message, details=exc.details),
        status=status.HTTP_409_CONFLICT,
    )


def not_found_error_response(exc: InventoryNotFound):
    from rest_framework import status
    from rest_framework.response import Response

    return Response(
        error_body(code=NOT_FOUND, message=exc.message),
        status=status.HTTP_404_NOT_FOUND,
    )


def notify_out_of_stock(sku_ids: list[UUID]) -> None:
    if not sku_ids:
        return
    for sku in SKU.objects.filter(id__in=sku_ids).only("id", "product_id"):
        emit_sku_out_of_stock_event(sku_id=sku.id, product_id=sku.product_id)
