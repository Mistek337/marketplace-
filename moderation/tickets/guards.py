from __future__ import annotations

from rest_framework.exceptions import PermissionDenied

from events.api_errors import error_body
from tickets.api_errors import TICKET_TERMINAL
from tickets.models import Ticket

TERMINAL_STATUSES = frozenset({Ticket.Status.HARD_BLOCKED})


def is_terminal(ticket: Ticket) -> bool:
    return ticket.status in TERMINAL_STATUSES


def reject_if_terminal(ticket: Ticket) -> None:
    if is_terminal(ticket):
        raise PermissionDenied(
            detail=error_body(
                code=TICKET_TERMINAL,
                message='Ticket is in a terminal status and cannot be modified',
            ),
        )
