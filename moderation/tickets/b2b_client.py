import json
import logging
import uuid
from datetime import datetime, timezone
from urllib import error, request

from django.conf import settings

logger = logging.getLogger(__name__)

EVENT_NAMESPACE = uuid.UUID('6ba7b810-9dad-11d1-80b4-00c04fd430c8')


class B2BClientError(Exception):
    pass


def moderated_idempotency_key(ticket_id: uuid.UUID) -> uuid.UUID:
    return uuid.uuid5(EVENT_NAMESPACE, f'ticket-approve:{ticket_id}')


def blocked_idempotency_key(ticket_id: uuid.UUID) -> uuid.UUID:
    return uuid.uuid5(EVENT_NAMESPACE, f'ticket-block:{ticket_id}')


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z')


def field_reports_for_b2b(reports: list[dict] | None) -> list[dict]:
    """ModerationEventRequest.field_reports: {field_name, comment, sku_id?}."""
    if not reports:
        return []
    normalized = []
    for item in reports:
        field_name = item.get('field_name') or item.get('field_path') or ''
        comment = item.get('comment') or item.get('message') or ''
        row = {'field_name': field_name, 'comment': comment}
        sku_id = item.get('sku_id')
        if sku_id:
            row['sku_id'] = str(sku_id)
        normalized.append(row)
    return normalized


def build_moderated_payload(
    *,
    ticket_id: uuid.UUID,
    product_id: uuid.UUID,
    moderator_comment: str = '',
) -> dict:
    """OpenAPI ModerationEventRequest для event_type=MODERATED."""
    payload = {
        'idempotency_key': str(moderated_idempotency_key(ticket_id)),
        'product_id': str(product_id),
        'event_type': 'MODERATED',
        'occurred_at': _now_iso(),
    }
    if moderator_comment:
        payload['moderator_comment'] = moderator_comment
    return payload


def build_blocked_payload(
    *,
    ticket_id: uuid.UUID,
    product_id: uuid.UUID,
    hard_block: bool,
    blocking_reason_id: uuid.UUID,
    moderator_comment: str = '',
    field_reports: list[dict] | None = None,
) -> dict:
    """OpenAPI ModerationEventRequest для event_type=BLOCKED."""
    payload = {
        'idempotency_key': str(blocked_idempotency_key(ticket_id)),
        'product_id': str(product_id),
        'event_type': 'BLOCKED',
        'occurred_at': _now_iso(),
        'hard_block': hard_block,
        'blocking_reason_id': str(blocking_reason_id),
    }
    if moderator_comment:
        payload['moderator_comment'] = moderator_comment
    b2b_reports = field_reports_for_b2b(field_reports)
    if b2b_reports:
        payload['field_reports'] = b2b_reports
    return payload


def deliver_b2b_payload(payload: dict) -> bool:
    base_url = (getattr(settings, 'B2B_BASE_URL', '') or '').rstrip('/')
    if not base_url:
        return False

    url = f'{base_url}/api/v1/moderation/events'
    body = json.dumps(payload).encode('utf-8')
    req = request.Request(url, data=body, method='POST')
    req.add_header('Content-Type', 'application/json')
    req.add_header('Accept', 'application/json')

    service_key = getattr(settings, 'MODERATION_TO_B2B_KEY', '') or ''
    if service_key:
        req.add_header('X-Service-Key', service_key)

    timeout = float(getattr(settings, 'B2B_TIMEOUT', 5))
    event = payload.get('event_type', payload.get('event', '?'))
    try:
        with request.urlopen(req, timeout=timeout):
            return True
    except error.URLError as exc:
        logger.warning('B2B unavailable (%s): %s', event, exc)
    except error.HTTPError as exc:
        logger.warning('B2B HTTP error %s (%s)', exc.code, event)
    return False


def deliver_moderated_payload(payload: dict) -> bool:
    return deliver_b2b_payload(payload)
