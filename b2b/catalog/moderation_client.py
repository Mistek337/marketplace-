import json
import uuid
from datetime import datetime, timezone
from urllib import error, request

from django.conf import settings


class ModerationClientError(Exception):
    pass


def emit_product_created_event(*, product_id, seller_id):
    base_url = (getattr(settings, "MODERATION_BASE_URL", "") or "").rstrip("/")
    if not base_url:
        return

    url = f"{base_url}/api/v1/events/product"
    payload = {
        "idempotency_key": str(uuid.uuid4()),
        "product_id": str(product_id),
        "seller_id": str(seller_id) if seller_id else None,
        "event": "CREATED",
        "date": datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
    }
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
            return
    except error.URLError as exc:
        raise ModerationClientError(f"Moderation unavailable: {exc}") from exc
    except error.HTTPError as exc:
        raise ModerationClientError(f"Moderation HTTP error: {exc.code}") from exc
