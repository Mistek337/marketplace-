from django.conf import settings
from rest_framework import status
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.response import Response
from rest_framework.views import APIView

from events.api_errors import CONFLICT, UNAUTHORIZED, error_body
from events.b2b_handlers import process_b2b_event
from events.serializers import IncomingB2BEventSerializer


class HealthAPIView(APIView):
    """GET /api/v1/health — проверка доступности сервиса."""

    authentication_classes = []
    permission_classes = []

    def get(self, request, *args, **kwargs):
        return Response({'status': 'ok'})


class B2BEventsAPIView(APIView):
    """POST /api/v1/b2b/events — приём событий от B2B."""

    authentication_classes = []
    permission_classes = []

    def _require_service_key(self, request) -> None:
        expected = getattr(settings, 'B2B_TO_MODERATION_KEY', '') or ''
        provided = request.headers.get('X-Service-Key') or request.META.get('HTTP_X_SERVICE_KEY')
        if not expected or provided != expected:
            raise AuthenticationFailed('Invalid service key')

    def post(self, request, *args, **kwargs):
        try:
            self._require_service_key(request)
        except AuthenticationFailed:
            return Response(
                error_body(code=UNAUTHORIZED, message='Authentication required'),
                status=status.HTTP_401_UNAUTHORIZED,
            )

        serializer = IncomingB2BEventSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        action = process_b2b_event(
            event_type=data['event_type'],
            idempotency_key=data['idempotency_key'],
            payload=data['payload'],
        )
        if action == 'duplicate':
            return Response(
                error_body(code=CONFLICT, message='Duplicate event'),
                status=status.HTTP_409_CONFLICT,
            )
        return Response(status=status.HTTP_202_ACCEPTED)
