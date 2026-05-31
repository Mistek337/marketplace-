from __future__ import annotations

import uuid

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import NotFound, PermissionDenied

from events.api_errors import error_body
from tickets.api_errors import NO_SKU, PRODUCT_EDITED_DURING_REVIEW, TICKET_NOT_ASSIGNED, TICKET_WRONG_STATUS
from tickets.b2b_client import build_moderated_payload, deliver_moderated_payload, moderated_idempotency_key
from tickets.models import B2BOutboxEvent, Moderator, Ticket


class ApproveConflict(Exception):
    def __init__(self, *, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


def ticket_has_sku(ticket: Ticket) -> bool:
    snapshot = ticket.json_after or {}
    skus = snapshot.get('skus') or snapshot.get('sku_list') or []
    if skus:
        return True
    return bool(snapshot.get('has_sku'))


def emit_moderated_event(ticket: Ticket) -> dict:
    idempotency_key = moderated_idempotency_key(ticket.id)
    payload = build_moderated_payload(
        ticket_id=ticket.id,
        product_id=ticket.product_id,
        seller_id=ticket.seller_id,
    )

    outbox, created = B2BOutboxEvent.objects.get_or_create(
        idempotency_key=idempotency_key,
        defaults={
            'ticket': ticket,
            'product_id': ticket.product_id,
            'seller_id': ticket.seller_id,
            'payload': payload,
        },
    )
    if outbox.sent_at:
        return outbox.payload

    if deliver_moderated_payload(payload):
        B2BOutboxEvent.objects.filter(pk=outbox.pk).update(sent_at=timezone.now())
    return payload


@transaction.atomic
def approve_ticket(*, ticket_id: uuid.UUID, moderator: Moderator, comment: str = '') -> Ticket:
    try:
        ticket = Ticket.objects.select_for_update().get(pk=ticket_id)
    except Ticket.DoesNotExist as exc:
        raise NotFound() from exc

    if ticket.status == Ticket.Status.HARD_BLOCKED:
        raise ApproveConflict(
            code=TICKET_WRONG_STATUS,
            message='Ticket is hard blocked',
        )

    if ticket.status != Ticket.Status.IN_REVIEW:
        raise ApproveConflict(
            code=TICKET_WRONG_STATUS,
            message='Ticket must be in IN_REVIEW',
        )

    if ticket.assigned_moderator_id != moderator.id:
        raise PermissionDenied(
            detail=error_body(
                code=TICKET_NOT_ASSIGNED,
                message='Ticket is assigned to another moderator',
            ),
        )

    if ticket.claimed_revision is None or ticket.product_revision != ticket.claimed_revision:
        raise ApproveConflict(
            code=PRODUCT_EDITED_DURING_REVIEW,
            message='Product was edited during review',
        )

    if not ticket_has_sku(ticket):
        raise ApproveConflict(
            code=NO_SKU,
            message='Product has no SKU',
        )

    ticket.status = Ticket.Status.APPROVED
    ticket.decision_at = timezone.now()
    if comment:
        ticket.decision_comment = comment
    ticket.save(update_fields=['status', 'decision_at', 'decision_comment', 'updated_at'])

    emit_moderated_event(ticket)
    return ticket
