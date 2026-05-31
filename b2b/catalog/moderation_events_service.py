"""Применение решения модерации (OpenAPI receiveModerationEvent)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import timedelta
from uuid import UUID

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from .b2c_client import emit_product_blocked_event
from .models import BlockingReason, ProcessedModerationEvent, Product, SKU

MODERATION_IDEMPOTENCY_TTL = timedelta(hours=24)
DEFAULT_MODERATION_SENDER_SERVICE = "moderation"


class ModerationEventInvalid(Exception):
    """Невалидное событие — OpenAPI 400 (не ретраить)."""

    def __init__(self, message: str, *, details: dict | None = None) -> None:
        self.message = message
        self.details = details
        super().__init__(message)


@dataclass(frozen=True)
class ApplyModerationResult:
    duplicate: bool
    product_id: UUID | None = None


def moderation_sender_service() -> str:
    return getattr(settings, "MODERATION_SENDER_SERVICE", None) or DEFAULT_MODERATION_SENDER_SERVICE


def _idempotency_cutoff():
    return timezone.now() - MODERATION_IDEMPOTENCY_TTL


def _purge_expired_processed(*, sender_service: str, idempotency_key: UUID) -> None:
    ProcessedModerationEvent.objects.filter(
        sender_service=sender_service,
        idempotency_key=idempotency_key,
        created_at__lt=_idempotency_cutoff(),
    ).delete()


def _find_processed_within_ttl(*, sender_service: str, idempotency_key: UUID):
    return (
        ProcessedModerationEvent.objects.filter(
            sender_service=sender_service,
            idempotency_key=idempotency_key,
            created_at__gte=_idempotency_cutoff(),
        )
        .first()
    )


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


def _resolve_blocking_reason(*, reason_id: UUID) -> None:
    if not BlockingReason.objects.filter(pk=reason_id).exists():
        raise ModerationEventInvalid(
            "Unknown blocking_reason_id",
            details={"blocking_reason_id": str(reason_id)},
        )


def apply_moderation_event(*, sender_service: str, data: dict) -> ApplyModerationResult:
    idempotency_key = data["idempotency_key"]
    product_id = data["product_id"]
    event_type = data["event_type"]
    occurred_at = data.get("occurred_at")

    _purge_expired_processed(
        sender_service=sender_service,
        idempotency_key=idempotency_key,
    )

    if _find_processed_within_ttl(
        sender_service=sender_service,
        idempotency_key=idempotency_key,
    ):
        return ApplyModerationResult(duplicate=True, product_id=product_id)

    if not Product.objects.filter(pk=product_id).exists():
        raise ModerationEventInvalid(
            "Unknown product_id",
            details={"product_id": str(product_id)},
        )

    if event_type == "BLOCKED":
        _resolve_blocking_reason(reason_id=data["blocking_reason_id"])

    try:
        with transaction.atomic():
            if _find_processed_within_ttl(
                sender_service=sender_service,
                idempotency_key=idempotency_key,
            ):
                return ApplyModerationResult(duplicate=True, product_id=product_id)

            try:
                ProcessedModerationEvent.objects.create(
                    sender_service=sender_service,
                    idempotency_key=idempotency_key,
                    event_type=event_type,
                    product_id=product_id,
                    occurred_at=occurred_at,
                )
            except IntegrityError:
                return ApplyModerationResult(duplicate=True, product_id=product_id)

            product = Product.objects.select_for_update().get(pk=product_id)

            if event_type == "MODERATED":
                product.status = Product.Status.MODERATED
                product.blocking_reason_id = None
                product.moderator_comment = ""
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
            blocking_reason_id = data["blocking_reason_id"]
            had_active_stock = _product_had_active_stock(product_id)

            product.status = (
                Product.Status.HARD_BLOCKED if hard_block else Product.Status.BLOCKED
            )
            product.blocking_reason_id = blocking_reason_id
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
