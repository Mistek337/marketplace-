from __future__ import annotations

import uuid

from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed

from tickets.models import Moderator


class ModeratorHeaderAuthentication(BaseAuthentication):
    """Локальная аутентификация модератора по заголовку X-Moderator-Id (для API и тестов)."""

    header_name = 'HTTP_X_MODERATOR_ID'

    def authenticate(self, request):
        raw = request.META.get(self.header_name)
        if not raw:
            return None
        try:
            moderator_id = uuid.UUID(str(raw))
        except ValueError as exc:
            raise AuthenticationFailed('Invalid moderator id') from exc
        try:
            moderator = Moderator.objects.get(pk=moderator_id, is_active=True)
        except Moderator.DoesNotExist as exc:
            raise AuthenticationFailed('Moderator not found') from exc
        return (moderator, None)
