import json
import uuid
from unittest.mock import patch

import pytest
from django.conf import settings

from tickets.models import BlockingReason, Ticket
from tickets.tests.conftest import bearer_headers


@pytest.fixture
def hard_reason(db):
    return BlockingReason.objects.create(
        code='FORBIDDEN_GOODS',
        title='Запрещённый товар',
        hard_block=True,
    )


def _service_headers() -> dict:
    return {'HTTP_X_SERVICE_KEY': settings.B2B_TO_MODERATION_KEY}


def _ticket_in_review(moderator, **kwargs) -> Ticket:
    defaults = {
        'product_id': uuid.uuid4(),
        'seller_id': uuid.uuid4(),
        'kind': Ticket.Kind.CREATE,
        'status': Ticket.Status.IN_REVIEW,
        'assigned_moderator': moderator,
        'json_after': {'title': 'Bad item', 'skus': [{'id': str(uuid.uuid4())}]},
        'product_revision': 1,
        'claimed_revision': 1,
    }
    defaults.update(kwargs)
    return Ticket.objects.create(**defaults)


@pytest.mark.django_db
@patch('tickets.services.deliver_b2b_payload', return_value=True)
def test_hard_block_transitions_to_terminal_and_emits_event(
    deliver_mock,
    api_client,
    moderator,
    hard_reason,
):
    ticket = _ticket_in_review(moderator)

    response = api_client.post(
        f'/api/v1/tickets/{ticket.id}/block/',
        data=json.dumps({
            'blocking_reason_ids': [str(hard_reason.id)],
            'comment': 'counterfeit',
            'field_reports': [
                {
                    'field_path': 'images[0].url',
                    'message': 'counterfeit logo',
                    'severity': 'ERROR',
                },
            ],
        }),
        content_type='application/json',
        **bearer_headers(moderator),
    )

    assert response.status_code == 200
    ticket.refresh_from_db()
    assert ticket.status == Ticket.Status.HARD_BLOCKED
    assert ticket.decision_at is not None
    assert len(ticket.field_reports) == 1
    assert ticket.field_reports[0]['field_path'] == 'images[0].url'

    deliver_mock.assert_called_once()
    payload = deliver_mock.call_args.args[0]
    assert payload['event'] == 'BLOCKED'
    assert payload['hard_block'] is True


@pytest.mark.django_db
@patch('tickets.services.deliver_b2b_payload', return_value=True)
def test_hard_block_event_carries_hard_block_true(
    deliver_mock,
    api_client,
    moderator,
    hard_reason,
):
    ticket = _ticket_in_review(moderator)

    api_client.post(
        f'/api/v1/tickets/{ticket.id}/block/',
        data=json.dumps({'blocking_reason_ids': [str(hard_reason.id)]}),
        content_type='application/json',
        **bearer_headers(moderator),
    )

    payload = deliver_mock.call_args.args[0]
    assert payload['hard_block'] is True
    assert str(hard_reason.id) in payload['blocking_reason_ids']


@pytest.mark.django_db
def test_any_modify_on_hard_blocked_returns_403(api_client, moderator, hard_reason):
    ticket = _ticket_in_review(moderator)
    ticket.status = Ticket.Status.HARD_BLOCKED
    ticket.save(update_fields=['status'])

    endpoints = [
        (f'/api/v1/tickets/{ticket.id}/approve/', None),
        (f'/api/v1/tickets/{ticket.id}/block/', {'blocking_reason_ids': [str(hard_reason.id)]}),
        (f'/api/v1/tickets/{ticket.id}/release/', None),
    ]

    for url, body in endpoints:
        response = api_client.post(
            url,
            data=json.dumps(body) if body else '',
            content_type='application/json',
            **bearer_headers(moderator),
        )
        assert response.status_code == 403, url
        assert response.json()['code'] == 'TICKET_TERMINAL'


@pytest.mark.django_db
def test_edited_event_on_hard_blocked_is_ignored(api_client, moderator):
    product_id = uuid.uuid4()
    ticket = Ticket.objects.create(
        product_id=product_id,
        seller_id=uuid.uuid4(),
        kind=Ticket.Kind.CREATE,
        status=Ticket.Status.HARD_BLOCKED,
        json_after={'title': 'blocked'},
        product_revision=5,
    )
    idempotency_key = uuid.uuid4()

    response = api_client.post(
        '/api/v1/b2b/events/',
        data=json.dumps({
            'event_type': 'PRODUCT_EDITED',
            'idempotency_key': str(idempotency_key),
            'occurred_at': '2026-05-31T12:00:00Z',
            'payload': {
                'product_id': str(product_id),
                'seller_id': str(ticket.seller_id),
                'json_before': {'title': 'blocked'},
                'json_after': {'title': 'seller tried to fix'},
            },
        }),
        content_type='application/json',
        **_service_headers(),
    )

    assert response.status_code == 202
    ticket.refresh_from_db()
    assert ticket.status == Ticket.Status.HARD_BLOCKED
    assert ticket.product_revision == 5
    assert ticket.json_after == {'title': 'blocked'}


@pytest.mark.django_db
def test_deleted_event_removes_hard_blocked(api_client, moderator):
    product_id = uuid.uuid4()
    ticket = Ticket.objects.create(
        product_id=product_id,
        seller_id=uuid.uuid4(),
        kind=Ticket.Kind.CREATE,
        status=Ticket.Status.HARD_BLOCKED,
        json_after={'title': 'blocked'},
    )
    ticket_id = ticket.id

    response = api_client.post(
        '/api/v1/b2b/events/',
        data=json.dumps({
            'event_type': 'PRODUCT_DELETED',
            'idempotency_key': str(uuid.uuid4()),
            'occurred_at': '2026-05-31T12:00:00Z',
            'payload': {'product_id': str(product_id)},
        }),
        content_type='application/json',
        **_service_headers(),
    )

    assert response.status_code == 202
    assert not Ticket.objects.filter(pk=ticket_id).exists()
