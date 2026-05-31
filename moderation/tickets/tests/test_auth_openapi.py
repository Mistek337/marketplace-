import json

import pytest
from django.contrib.auth.hashers import make_password

from tickets.models import Moderator
from tickets.tests.conftest import bearer_headers, make_moderator


@pytest.mark.django_db
def test_login_returns_token_response(api_client):
    moderator = Moderator.objects.create(
        email='login@example.com',
        password=make_password('secret-password'),
        first_name='Ann',
        role=Moderator.Role.MODERATOR,
    )

    response = api_client.post(
        '/api/v1/auth/login/',
        data=json.dumps({'email': 'login@example.com', 'password': 'secret-password'}),
        content_type='application/json',
    )

    assert response.status_code == 200
    body = response.json()
    assert body['token_type'] == 'Bearer'
    assert body['access_token']
    assert body['refresh_token']
    assert body['expires_in'] == 3600
    assert body['user_id'] == str(moderator.id)
    assert body['role'] == 'MODERATOR'

    moderator.refresh_from_db()
    assert moderator.last_login_at is not None


@pytest.mark.django_db
def test_ticket_endpoints_require_bearer(api_client, moderators):
    moderator, _ = moderators
    from tickets.models import Ticket
    import uuid

    ticket = Ticket.objects.create(
        product_id=uuid.uuid4(),
        seller_id=uuid.uuid4(),
        kind=Ticket.Kind.CREATE,
        status=Ticket.Status.IN_REVIEW,
        assigned_moderator=moderator,
        json_after={'skus': [{'id': '1'}]},
        claimed_revision=1,
        product_revision=1,
    )

    response = api_client.post(f'/api/v1/tickets/{ticket.id}/approve/')
    assert response.status_code == 401

    response = api_client.post(
        f'/api/v1/tickets/{ticket.id}/approve/',
        **bearer_headers(moderator),
    )
    assert response.status_code in (200, 409)
