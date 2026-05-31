from __future__ import annotations

import uuid

from django.db import transaction

from tickets.models import Ticket


class DuplicateB2BEvent(Exception):
    pass


@transaction.atomic
def process_b2b_event(
    *,
    event_type: str,
    idempotency_key: uuid.UUID,
    payload: dict,
) -> str:
    """
    Обработка PRODUCT_* от B2B.
    Возвращает action: created | updated | ignored | deleted | duplicate.
    """
    from events.models import ProcessedB2BEvent

    if ProcessedB2BEvent.objects.filter(idempotency_key=idempotency_key).exists():
        return 'duplicate'

    product_id = uuid.UUID(str(payload['product_id']))

    if event_type == 'PRODUCT_DELETED':
        Ticket.objects.filter(product_id=product_id).delete()
        ProcessedB2BEvent.objects.create(
            idempotency_key=idempotency_key,
            event_type=event_type,
            product_id=product_id,
        )
        return 'deleted'

    hard_blocked = Ticket.objects.filter(
        product_id=product_id,
        status=Ticket.Status.HARD_BLOCKED,
    ).exists()

    if event_type == 'PRODUCT_EDITED' and hard_blocked:
        ProcessedB2BEvent.objects.create(
            idempotency_key=idempotency_key,
            event_type=event_type,
            product_id=product_id,
        )
        return 'ignored'

    if event_type in ('PRODUCT_CREATED', 'PRODUCT_EDITED'):
        seller_id = uuid.UUID(str(payload['seller_id']))
        json_after = payload.get('json_after') or {}
        json_before = payload.get('json_before')
        category_id = payload.get('category_id')
        category_uuid = uuid.UUID(str(category_id)) if category_id else None
        kind = Ticket.Kind.CREATE if event_type == 'PRODUCT_CREATED' else Ticket.Kind.EDIT

        ticket = (
            Ticket.objects.filter(product_id=product_id)
            .exclude(status=Ticket.Status.HARD_BLOCKED)
            .order_by('-created_at')
            .first()
        )
        if ticket and ticket.status in (Ticket.Status.PENDING, Ticket.Status.IN_REVIEW, Ticket.Status.BLOCKED):
            ticket.product_revision += 1
            ticket.json_after = json_after
            if json_before is not None:
                ticket.json_before = json_before
            ticket.kind = kind
            ticket.seller_id = seller_id
            ticket.category_id = category_uuid
            ticket.save(
                update_fields=[
                    'product_revision',
                    'json_after',
                    'json_before',
                    'kind',
                    'seller_id',
                    'category_id',
                    'updated_at',
                ],
            )
            action = 'updated'
        else:
            Ticket.objects.create(
                product_id=product_id,
                seller_id=seller_id,
                category_id=category_uuid,
                kind=kind,
                status=Ticket.Status.PENDING,
                json_before=json_before,
                json_after=json_after,
                product_revision=1,
                queue_priority=int(payload.get('queue_priority') or 3),
            )
            action = 'created'
        ProcessedB2BEvent.objects.create(
            idempotency_key=idempotency_key,
            event_type=event_type,
            product_id=product_id,
        )
        return action

    ProcessedB2BEvent.objects.create(
        idempotency_key=idempotency_key,
        event_type=event_type,
        product_id=product_id,
    )
    return 'ignored'
