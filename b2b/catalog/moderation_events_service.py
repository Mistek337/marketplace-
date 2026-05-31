"""Применение решения модерации (OpenAPI receiveModerationEvent)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from uuid import UUID

from django.db import IntegrityError, transaction
from django.utils import timezone

from .b2c_client import emit_product_blocked_event
from .models import BlockingReason, ProcessedModerationEvent, Product, SKU


class ModerationEventNotFound(Exception):
    def __init__(self, product_id: UUID) -> None:
        self.product_id = product_id


@dataclass(frozen=True)
class ApplyModerationResult:
    duplicate: bool
    product_id: UUID | None = None


def _normalize_field_reports(raw_reports) -> list[dict]:
    if not raw_reports:
        return []
    normalized = []
    for row in raw_reports:
        sku_id = row.get("sku_id")
        normalized.append(
            {
                "field_name": row["field_name"],
                "sku_id": str(sku_id) if sku_id else None,
                "comment": row["comment"],
            }
        )
    return normalized


def _product_had_active_stock(product_id: UUID) -> bool:
    return SKU.objects.filter(product_id=product_id, active_quantity__gt=0).exists()


def _ensure_blocking_reason(*, reason_id: UUID, moderator_comment: str | None) -> None:
    comment = (moderator_comment or "").strip()
    BlockingReason.objects.get_or_create(
        id=reason_id,
        defaults={
            "title": "Blocked by moderation",
            "comment": comment or "Product blocked",
        },
    )


def apply_moderation_event(*, data: dict) -> ApplyModerationResult:
    idempotency_key = data["idempotency_key"]
    product_id = data["product_id"]
    event_type = data["event_type"]

    if ProcessedModerationEvent.objects.filter(idempotency_key=idempotency_key).exists():
        return ApplyModerationResult(duplicate=True, product_id=product_id)

    try:
        with transaction.atomic():
            try:
                ProcessedModerationEvent.objects.create(
                    idempotency_key=idempotency_key,
                    event_type=event_type,
                    product_id=product_id,
                )
            except IntegrityError:
                return ApplyModerationResult(duplicate=True, product_id=product_id)

            try:
                product = Product.objects.select_for_update().get(pk=product_id)
            except Product.DoesNotExist as exc:
                raise ModerationEventNotFound(product_id) from exc

            if event_type == "MODERATED":
                product.status = Product.Status.MODERATED
                product.blocking_reason_id = None
                product.moderator_comment = (data.get("moderator_comment") or "").strip()
                product.field_reports = []
                product.updated_at = timezone.now()
                product.save(
                    update_fields=[
                        "status",
                        "blocking_reason_id",
                        "moderator_comment",
                        "field_reports",
                        "updated_at",
                    ]
                )
                return ApplyModerationResult(duplicate=False, product_id=product_id)

            hard_block = bool(data.get("hard_block", False))
            had_active_stock = _product_had_active_stock(product_id)
            _ensure_blocking_reason(
                reason_id=data["blocking_reason_id"],
                moderator_comment=data.get("moderator_comment"),
            )
            product.status = (
                Product.Status.HARD_BLOCKED if hard_block else Product.Status.BLOCKED
            )
            product.blocking_reason_id = data["blocking_reason_id"]
            product.moderator_comment = (data.get("moderator_comment") or "").strip()
            product.field_reports = _normalize_field_reports(data.get("field_reports"))
            product.updated_at = timezone.now()
            product.save(
                update_fields=[
                    "status",
                    "blocking_reason_id",
                    "moderator_comment",
                    "field_reports",
                    "updated_at",
                ]
            )

            if had_active_stock:
                b2c_key = uuid.uuid5(idempotency_key, "b2c-product-blocked")
                emit_product_blocked_event(
                    product_id=product_id,
                    hard_block=hard_block,
                    idempotency_key=b2c_key,
                )

            return ApplyModerationResult(duplicate=False, product_id=product_id)
    except IntegrityError:
        return ApplyModerationResult(duplicate=True, product_id=product_id)
