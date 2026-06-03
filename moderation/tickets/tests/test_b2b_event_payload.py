"""Форма исходящих событий → OpenAPI ModerationEventRequest."""

import uuid

from tickets.b2b_client import build_blocked_payload, build_moderated_payload


def test_moderated_payload_matches_openapi():
    ticket_id = uuid.uuid4()
    product_id = uuid.uuid4()
    payload = build_moderated_payload(
        ticket_id=ticket_id,
        product_id=product_id,
        moderator_comment='approved',
    )

    assert payload['event_type'] == 'MODERATED'
    assert payload['occurred_at']
    assert payload['product_id'] == str(product_id)
    assert payload['idempotency_key']
    assert payload['moderator_comment'] == 'approved'
    assert 'event' not in payload
    assert 'date' not in payload
    assert 'seller_id' not in payload


def test_blocked_payload_matches_openapi():
    ticket_id = uuid.uuid4()
    product_id = uuid.uuid4()
    reason_id = uuid.uuid4()
    payload = build_blocked_payload(
        ticket_id=ticket_id,
        product_id=product_id,
        hard_block=True,
        blocking_reason_id=reason_id,
        moderator_comment='blocked',
        field_reports=[{'field_path': 'title', 'message': 'fix title'}],
    )

    assert payload['event_type'] == 'BLOCKED'
    assert payload['occurred_at']
    assert payload['hard_block'] is True
    assert payload['blocking_reason_id'] == str(reason_id)
    assert payload['moderator_comment'] == 'blocked'
    assert payload['field_reports'] == [
        {'field_name': 'title', 'comment': 'fix title'},
    ]
    assert 'blocking_reason_ids' not in payload
    assert 'event' not in payload
    assert 'date' not in payload
