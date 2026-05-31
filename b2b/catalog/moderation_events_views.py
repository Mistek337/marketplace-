"""POST /api/v1/moderation/events — приём MODERATED/BLOCKED от Moderation."""

from __future__ import annotations

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .api_errors import NOT_FOUND, drf_validation_error, error_body
from .moderation_events_serializers import ModerationEventRequestSerializer
from .moderation_events_service import (
    ApplyModerationResult,
    ModerationEventNotFound,
    apply_moderation_event,
)
from .public_catalog import require_moderation_service_key


class ReceiveModerationEventAPIView(APIView):
    """OpenAPI receiveModerationEvent — 204 при успехе или дубликате."""

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
            result: ApplyModerationResult = apply_moderation_event(
                data=serializer.validated_data
            )
        except ModerationEventNotFound as exc:
            return Response(
                error_body(
                    code=NOT_FOUND,
                    message=f"Product {exc.product_id} not found",
                ),
                status=status.HTTP_404_NOT_FOUND,
            )

        if result.duplicate:
            return Response(status=status.HTTP_204_NO_CONTENT)
        return Response(status=status.HTTP_204_NO_CONTENT)
