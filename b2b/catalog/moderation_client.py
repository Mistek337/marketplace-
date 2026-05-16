import json
import logging
import uuid
from datetime import datetime, timezone
from urllib import error, request

from django.conf import settings
from django.utils import timezone as django_tz

logger = logging.getLogger(__name__)


class ModerationClientError(Exception):
    pass


def _build_product_event_payload(*, product_id, seller_id, event: str, idempotency_key: uuid.UUID) -> dict:
    return {
        "idempotency_key": str(idempotency_key),
        "product_id": str(product_id),
        "seller_id": str(seller_id) if seller_id else None,
        "event": event,
        "date": datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
    }


def _deliver_moderation_payload(payload: dict) -> bool:
    """POST на будущий Moderation; False, если URL не задан или доставка не удалась."""
    base_url = (getattr(settings, "MODERATION_BASE_URL", "") or "").rstrip("/")
    if not base_url:
        return False

    url = f"{base_url}/api/v1/events/product"
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json")

    service_key = getattr(settings, "B2B_TO_MODERATION_KEY", "") or ""
    if service_key:
        req.add_header("X-Service-Key", service_key)

    timeout = float(getattr(settings, "MODERATION_TIMEOUT", 5))
    try:
        with request.urlopen(req, timeout=timeout):
            return True
    except error.URLError as exc:
        logger.warning(
            "Moderation unavailable (product %s event): %s",
            payload.get("event"),
            exc,
        )
    except error.HTTPError as exc:
        logger.warning(
            "Moderation HTTP error %s (product %s event)",
            exc.code,
            payload.get("event"),
        )
    return False


def _emit_product_event(*, product_id, seller_id, event: str) -> None:
    from .models import ModerationOutboxEvent

    idempotency_key = uuid.uuid4()
    payload = _build_product_event_payload(
        product_id=product_id,
        seller_id=seller_id,
        event=event,
        idempotency_key=idempotency_key,
    )
    outbox = ModerationOutboxEvent.objects.create(
        idempotency_key=idempotency_key,
        event=event,
        product_id=product_id,
        seller_id=seller_id,
        payload=payload,
    )
    if _deliver_moderation_payload(payload):
        ModerationOutboxEvent.objects.filter(pk=outbox.pk).update(sent_at=django_tz.now())


def emit_product_created_event(*, product_id, seller_id) -> None:
    _emit_product_event(product_id=product_id, seller_id=seller_id, event="CREATED")


def emit_product_edited_event(*, product_id, seller_id) -> None:
    _emit_product_event(product_id=product_id, seller_id=seller_id, event="EDITED")
