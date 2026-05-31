import jwt
from django.conf import settings
from rest_framework import authentication, exceptions

from tickets.models import Moderator


class ModeratorJWTAuthentication(authentication.BaseAuthentication):
    """OpenAPI security: bearerAuth."""

    def authenticate(self, request):
        header = request.headers.get('Authorization', '')
        if not header.startswith('Bearer '):
            return None

        token = header.split(' ', 1)[1].strip()
        if not token:
            raise exceptions.AuthenticationFailed('Invalid token')

        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
        except jwt.PyJWTError as exc:
            raise exceptions.AuthenticationFailed('Invalid token') from exc

        if payload.get('token_type') != 'access':
            raise exceptions.AuthenticationFailed('Invalid token')

        user_id = payload.get('user_id')
        if not user_id:
            raise exceptions.AuthenticationFailed('Invalid token')

        try:
            moderator = Moderator.objects.get(id=user_id, is_active=True)
        except Moderator.DoesNotExist as exc:
            raise exceptions.AuthenticationFailed('Invalid token') from exc

        return (moderator, token)
