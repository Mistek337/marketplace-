from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt
from django.conf import settings

ACCESS_TOKEN_MINUTES = 60
REFRESH_TOKEN_MINUTES = 60 * 24 * 14


def build_moderator_token(*, moderator_id, role: str, token_type: str, lifetime_minutes: int) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        'token_type': token_type,
        'user_id': str(moderator_id),
        'role': role,
        'jti': str(uuid4()),
        'iat': int(now.timestamp()),
        'exp': int((now + timedelta(minutes=lifetime_minutes)).timestamp()),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm='HS256')


def build_access_token(*, moderator_id, role: str) -> str:
    return build_moderator_token(
        moderator_id=moderator_id,
        role=role,
        token_type='access',
        lifetime_minutes=ACCESS_TOKEN_MINUTES,
    )


def build_refresh_token(*, moderator_id, role: str) -> str:
    return build_moderator_token(
        moderator_id=moderator_id,
        role=role,
        token_type='refresh',
        lifetime_minutes=REFRESH_TOKEN_MINUTES,
    )
