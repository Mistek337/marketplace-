import json
import uuid
from unittest.mock import patch

import pytest

from tickets.models import B2BOutboxEvent, Ticket
from tickets.tests.conftest import bearer_headers


def _create_ticket(
    *,
    moderator,
    product_revision: int = 1,
    claimed_revision: int = 1,
    with_sku: bool = True,
    status: str = Ticket.Status.IN_REVIEW,
) -> Ticket:
    json_after = {'title': 'Demo', 'skus': [{'id': str(uuid.uuid4())}]} if with_sku else {'title': 'Demo', 'skus': []}
    return Ticket.objects.create(
        product_id=uuid.uuid4(),
        seller_id=uuid.uuid4(),
        kind=Ticket.Kind.CREATE,
        status=status,
        assigned_moderator=moderator,
        json_after=json_after,
        product_revision=product_revision,
        claimed_revision=claimed_revision,
    )


@pytest.mark.django_db
@patch('tickets.services.deliver_b2b_payload', return_value=True)
def test_approve_transitions_to_moderated_and_emits_event(
    deliver_mock,
    api_client,
    moderators,
):
    moderator, _ = moderators
    ticket = _create_ticket(moderator=moderator)

    response = api_client.post(
        f'/api/v1/tickets/{ticket.id}/approve/',
        data=json.dumps({'comment': 'ok'}),
        content_type='application/json',
        **bearer_headers(moderator),
    )

    assert response.status_code == 200
    ticket.refresh_from_db()
    assert ticket.status == Ticket.Status.APPROVED
    assert ticket.decision_at is not None

    deliver_mock.assert_called_once()
    payload = deliver_mock.call_args.args[0]
    assert payload['event_type'] == 'MODERATED'
    assert payload['product_id'] == str(ticket.product_id)
    assert payload['idempotency_key']
    assert payload['occurred_at']
    assert payload['moderator_comment'] == 'ok'
    assert 'event' not in payload
    assert 'date' not in payload
    assert 'seller_id' not in payload

    outbox = B2BOutboxEvent.objects.get(ticket=ticket)
    assert outbox.sent_at is not None
    assert outbox.payload['event_type'] == 'MODERATED'
    assert 'event' not in outbox.payload
    assert 'date' not in outbox.payload


@pytest.mark.django_db
def test_approve_others_card_returns_409(api_client, moderators):
    owner, other = moderators
    ticket = _create_ticket(moderator=owner)

    response = api_client.post(
        f'/api/v1/tickets/{ticket.id}/approve/',
        **bearer_headers(other),
    )

    assert response.status_code == 409
    body = response.json()
    assert body['code'] == 'TICKET_WRONG_STATUS'
    ticket.refresh_from_db()
    assert ticket.status == Ticket.Status.IN_REVIEW


@pytest.mark.django_db
def test_approve_after_edited_returns_409(api_client, moderators):
    moderator, _ = moderators
    ticket = _create_ticket(moderator=moderator, product_revision=2, claimed_revision=1)

    response = api_client.post(
        f'/api/v1/tickets/{ticket.id}/approve/',
        **bearer_headers(moderator),
    )

    assert response.status_code == 409
    body = response.json()
    assert body['code'] == 'PRODUCT_EDITED_DURING_REVIEW'
    ticket.refresh_from_db()
    assert ticket.status == Ticket.Status.IN_REVIEW


@pytest.mark.django_db
def test_approve_without_sku_returns_409(api_client, moderators):
    moderator, _ = moderators
    ticket = _create_ticket(moderator=moderator, with_sku=False)

    response = api_client.post(
        f'/api/v1/tickets/{ticket.id}/approve/',
        **bearer_headers(moderator),
    )

    assert response.status_code == 409
    body = response.json()
    assert body['code'] == 'NO_SKU'
    ticket.refresh_from_db()
    assert ticket.status == Ticket.Status.IN_REVIEW
