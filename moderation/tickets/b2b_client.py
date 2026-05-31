import json
import logging
import uuid
from datetime import datetime, timezone
from urllib import error, request

from django.conf import settings

logger = logging.getLogger(__name__)

MODERATED_NAMESPACE = uuid.UUID('6ba7b810-9dad-11d1-80b4-00c04fd430c8')


class B2BClientError(Exception):
    pass


def moderated_idempotency_key(ticket_id: uuid.UUID) -> uuid.UUID:
    return uuid.uuid5(MODERATED_NAMESPACE, f'ticket-approve:{ticket_id}')


def build_moderated_payload(*, ticket_id: uuid.UUID, product_id: uuid.UUID, seller_id: uuid.UUID) -> dict:
    idempotency_key = moderated_idempotency_key(ticket_id)
    return {
        'idempotency_key': str(idempotency_key),
        'product_id': str(product_id),
        'seller_id': str(seller_id),
        'event': 'MODERATED',
        'date': datetime.now(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z'),
    }


def deliver_moderated_payload(payload: dict) -> bool:
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
    try:
        with request.urlopen(req, timeout=timeout):
            return True
    except error.URLError as exc:
        logger.warning('B2B unavailable (MODERATED): %s', exc)
    except error.HTTPError as exc:
        logger.warning('B2B HTTP error %s (MODERATED)', exc.code)
    return False
