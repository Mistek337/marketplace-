from django.conf import settings
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed


class B2BServiceKeyAuthentication(BaseAuthentication):
    """X-Service-Key от B2B (B2B_TO_MODERATION_KEY)."""

    def authenticate(self, request):
        expected = getattr(settings, 'B2B_TO_MODERATION_KEY', '') or ''
        if not expected:
            return None

        provided = request.headers.get('X-Service-Key') or request.META.get('HTTP_X_SERVICE_KEY')
        if not provided:
            return None
        if provided != expected:
            raise AuthenticationFailed('Invalid service key')
        return (None, None)
