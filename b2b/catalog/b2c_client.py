"""Доставка событий B2B → B2C (OpenAPI: outbox + idempotency_key)."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from urllib import error, request

from django.conf import settings
from django.utils import timezone as django_tz

logger = logging.getLogger(__name__)


def _iso_z_now() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


def _build_sku_out_of_stock_payload(*, sku_id, product_id, idempotency_key: uuid.UUID) -> dict:
    return {
        "idempotency_key": str(idempotency_key),
        "event": "SKU_OUT_OF_STOCK",
        "sku_id": str(sku_id),
        "product_id": str(product_id),
        "date": _iso_z_now(),
    }


def _deliver_b2c_payload(payload: dict) -> bool:
    base_url = (getattr(settings, "B2C_EVENTS_BASE_URL", "") or "").rstrip("/")
    if not base_url:
        return False

    url = f"{base_url}/api/v1/events/inventory"
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json")

    service_key = getattr(settings, "B2B_TO_B2C_KEY", "") or ""
    if service_key:
        req.add_header("X-Service-Key", service_key)

    timeout = float(getattr(settings, "B2C_EVENTS_TIMEOUT", 5))
    try:
        with request.urlopen(req, timeout=timeout):
            return True
    except error.URLError as exc:
        logger.warning("B2C events unavailable (%s): %s", payload.get("event"), exc)
    except error.HTTPError as exc:
        logger.warning("B2C events HTTP error %s (%s)", exc.code, payload.get("event"))
    return False


def _build_product_blocked_payload(
    *,
    product_id,
    hard_block: bool,
    idempotency_key: uuid.UUID,
) -> dict:
    return {
        "idempotency_key": str(idempotency_key),
        "event": "PRODUCT_BLOCKED",
        "product_id": str(product_id),
        "hard_block": hard_block,
        "date": _iso_z_now(),
    }


def _deliver_b2c_product_payload(payload: dict) -> bool:
    base_url = (getattr(settings, "B2C_EVENTS_BASE_URL", "") or "").rstrip("/")
    if not base_url:
        return False

    url = f"{base_url}/api/v1/events/product"
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json")

    service_key = getattr(settings, "B2B_TO_B2C_KEY", "") or ""
    if service_key:
        req.add_header("X-Service-Key", service_key)

    timeout = float(getattr(settings, "B2C_EVENTS_TIMEOUT", 5))
    try:
        with request.urlopen(req, timeout=timeout):
            return True
    except error.URLError as exc:
        logger.warning("B2C events unavailable (%s): %s", payload.get("event"), exc)
    except error.HTTPError as exc:
        logger.warning("B2C events HTTP error %s (%s)", exc.code, payload.get("event"))
    return False


def emit_product_blocked_event(*, product_id, hard_block: bool, idempotency_key: uuid.UUID) -> None:
    from .models import B2COutboxEvent

    payload = _build_product_blocked_payload(
        product_id=product_id,
        hard_block=hard_block,
        idempotency_key=idempotency_key,
    )
    outbox = B2COutboxEvent.objects.create(
        idempotency_key=idempotency_key,
        event="PRODUCT_BLOCKED",
        sku_id=None,
        product_id=product_id,
        payload=payload,
    )
    if _deliver_b2c_product_payload(payload):
        B2COutboxEvent.objects.filter(pk=outbox.pk).update(sent_at=django_tz.now())


def emit_sku_out_of_stock_event(*, sku_id, product_id) -> None:
    from .models import B2COutboxEvent

    idempotency_key = uuid.uuid4()
    payload = _build_sku_out_of_stock_payload(
        sku_id=sku_id,
        product_id=product_id,
        idempotency_key=idempotency_key,
    )
    outbox = B2COutboxEvent.objects.create(
        idempotency_key=idempotency_key,
        event="SKU_OUT_OF_STOCK",
        sku_id=sku_id,
        product_id=product_id,
        payload=payload,
    )
    if _deliver_b2c_payload(payload):
        B2COutboxEvent.objects.filter(pk=outbox.pk).update(sent_at=django_tz.now())
