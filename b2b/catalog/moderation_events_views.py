"""POST /api/v1/moderation/events — приём MODERATED/BLOCKED от Moderation."""

from __future__ import annotations

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .api_errors import VALIDATION_ERROR, drf_validation_error, error_body
from .moderation_events_serializers import ModerationEventRequestSerializer
from .moderation_events_service import (
    ApplyModerationResult,
    ModerationEventInvalid,
    apply_moderation_event,
    moderation_sender_service,
)
from .public_catalog import require_moderation_service_key


class ReceiveModerationEventAPIView(APIView):
    """OpenAPI receiveModerationEvent — только 204 / 400 / 401."""

    def post(self, request, *args, **kwargs):
        denied = require_moderation_service_key(request)
        if denied is not None:
            return denied

        serializer = ModerationEventRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                drf_validation_error(serializer.errors),
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            apply_moderation_event(
                sender_service=moderation_sender_service(),
                data=serializer.validated_data,
            )
        except ModerationEventInvalid as exc:
            return Response(
                error_body(
                    code=VALIDATION_ERROR,
                    message=exc.message,
                    details=exc.details,
                ),
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(status=status.HTTP_204_NO_CONTENT)
