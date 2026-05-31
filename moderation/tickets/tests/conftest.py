import pytest
from django.contrib.auth.hashers import make_password

from tickets.auth_tokens import build_access_token
from tickets.models import Moderator


@pytest.fixture
def api_client():
    from django.test import Client
    return Client()


def make_moderator(*, email: str) -> Moderator:
    return Moderator.objects.create(
        email=email,
        password=make_password('demo-demo-demo'),
        first_name='Test',
        last_name='Moderator',
        role=Moderator.Role.MODERATOR,
    )


@pytest.fixture
def moderators(db):
    return make_moderator(email='mod-a@example.com'), make_moderator(email='mod-b@example.com')


@pytest.fixture
def moderator(db):
    return make_moderator(email='mod-hard@example.com')


def bearer_headers(moderator: Moderator) -> dict:
    token = build_access_token(moderator_id=moderator.id, role=moderator.role)
    return {'HTTP_AUTHORIZATION': f'Bearer {token}'}
