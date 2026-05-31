from __future__ import annotations

import uuid

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import NotFound

from tickets.api_errors import (
    INVALID_BLOCKING_REASON,
    NO_SKU,
    PRODUCT_EDITED_DURING_REVIEW,
    TICKET_WRONG_STATUS,
)
from tickets.b2b_client import (
    blocked_idempotency_key,
    build_blocked_payload,
    build_moderated_payload,
    deliver_b2b_payload,
    moderated_idempotency_key,
)
from tickets.guards import reject_if_terminal
from tickets.models import B2BOutboxEvent, BlockingReason, Moderator, Ticket


class TicketFlowConflict(Exception):
    def __init__(self, *, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


# Backward-compatible alias for approve tests
ApproveConflict = TicketFlowConflict


def ticket_has_sku(ticket: Ticket) -> bool:
    snapshot = ticket.json_after or {}
    skus = snapshot.get('skus') or snapshot.get('sku_list') or []
    if skus:
        return True
    return bool(snapshot.get('has_sku'))


def _emit_outbox_event(*, ticket: Ticket, event: str, payload: dict, idempotency_key: uuid.UUID) -> dict:
    outbox, _ = B2BOutboxEvent.objects.get_or_create(
        idempotency_key=idempotency_key,
        defaults={
            'ticket': ticket,
            'event': event,
            'product_id': ticket.product_id,
            'seller_id': ticket.seller_id,
            'payload': payload,
        },
    )
    if outbox.sent_at:
        return outbox.payload

    if deliver_b2b_payload(payload):
        B2BOutboxEvent.objects.filter(pk=outbox.pk).update(sent_at=timezone.now())
    return payload


def emit_moderated_event(ticket: Ticket) -> dict:
    payload = build_moderated_payload(
        ticket_id=ticket.id,
        product_id=ticket.product_id,
        seller_id=ticket.seller_id,
    )
    return _emit_outbox_event(
        ticket=ticket,
        event='MODERATED',
        payload=payload,
        idempotency_key=moderated_idempotency_key(ticket.id),
    )


def emit_blocked_event(
    ticket: Ticket,
    *,
    hard_block: bool,
    blocking_reason_ids: list[uuid.UUID],
    comment: str = '',
) -> dict:
    payload = build_blocked_payload(
        ticket_id=ticket.id,
        product_id=ticket.product_id,
        seller_id=ticket.seller_id,
        hard_block=hard_block,
        blocking_reason_ids=blocking_reason_ids,
        comment=comment,
    )
    return _emit_outbox_event(
        ticket=ticket,
        event='BLOCKED',
        payload=payload,
        idempotency_key=blocked_idempotency_key(ticket.id),
    )


def _ensure_in_review_assigned(ticket: Ticket, moderator: Moderator) -> None:
    reject_if_terminal(ticket)

    if ticket.status != Ticket.Status.IN_REVIEW:
        raise TicketFlowConflict(
            code=TICKET_WRONG_STATUS,
            message='Ticket must be in IN_REVIEW',
        )

    if ticket.assigned_moderator_id != moderator.id:
        raise TicketFlowConflict(
            code=TICKET_WRONG_STATUS,
            message='Ticket is assigned to another moderator',
        )


@transaction.atomic
def approve_ticket(*, ticket_id: uuid.UUID, moderator: Moderator, comment: str = '') -> Ticket:
    try:
        ticket = Ticket.objects.select_for_update().get(pk=ticket_id)
    except Ticket.DoesNotExist as exc:
        raise NotFound() from exc

    _ensure_in_review_assigned(ticket, moderator)

    if ticket.claimed_revision is None or ticket.product_revision != ticket.claimed_revision:
        raise TicketFlowConflict(
            code=PRODUCT_EDITED_DURING_REVIEW,
            message='Product was edited during review',
        )

    if not ticket_has_sku(ticket):
        raise TicketFlowConflict(
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


@transaction.atomic
def block_ticket(
    *,
    ticket_id: uuid.UUID,
    moderator: Moderator,
    blocking_reason_ids: list[uuid.UUID],
    comment: str = '',
    field_reports: list[dict] | None = None,
) -> Ticket:
    try:
        ticket = Ticket.objects.select_for_update().get(pk=ticket_id)
    except Ticket.DoesNotExist as exc:
        raise NotFound() from exc

    _ensure_in_review_assigned(ticket, moderator)

    reasons = list(
        BlockingReason.objects.filter(id__in=blocking_reason_ids, is_active=True),
    )
    if len(reasons) != len(set(blocking_reason_ids)):
        raise TicketFlowConflict(
            code=INVALID_BLOCKING_REASON,
            message='One or more blocking reasons are invalid',
        )

    is_hard = any(reason.hard_block for reason in reasons)
    ticket.status = Ticket.Status.HARD_BLOCKED if is_hard else Ticket.Status.BLOCKED
    ticket.decision_at = timezone.now()
    if comment:
        ticket.decision_comment = comment
    if field_reports is not None:
        ticket.field_reports = field_reports
    ticket.save(
        update_fields=['status', 'decision_at', 'decision_comment', 'field_reports', 'updated_at'],
    )

    emit_blocked_event(
        ticket,
        hard_block=is_hard,
        blocking_reason_ids=[reason.id for reason in reasons],
        comment=comment,
    )
    return ticket


# Alias for backward compatibility
decline_ticket = block_ticket


@transaction.atomic
def release_ticket(*, ticket_id: uuid.UUID, moderator: Moderator) -> Ticket:
    try:
        ticket = Ticket.objects.select_for_update().get(pk=ticket_id)
    except Ticket.DoesNotExist as exc:
        raise NotFound() from exc

    _ensure_in_review_assigned(ticket, moderator)

    ticket.status = Ticket.Status.PENDING
    ticket.assigned_moderator = None
    ticket.claimed_revision = None
    ticket.claimed_at = None
    ticket.save(
        update_fields=[
            'status',
            'assigned_moderator',
            'claimed_revision',
            'claimed_at',
            'updated_at',
        ],
    )
    return ticket
