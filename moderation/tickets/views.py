from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from events.api_errors import error_body
from tickets.auth import ModeratorJWTAuthentication
from tickets.serializers import (
    ApproveRequestSerializer,
    BlockDecisionRequestSerializer,
    TicketResponseSerializer,
)
from tickets.services import TicketFlowConflict, approve_ticket, block_ticket, release_ticket


class _TicketActionAPIView(APIView):
    authentication_classes = [ModeratorJWTAuthentication]
    permission_classes = [IsAuthenticated]

    def _conflict_response(self, exc: TicketFlowConflict) -> Response:
        return Response(
            error_body(code=exc.code, message=exc.message),
            status=status.HTTP_409_CONFLICT,
        )


class TicketApproveAPIView(_TicketActionAPIView):
    """POST /api/v1/tickets/{ticket_id}/approve — OpenAPI Tickets tag."""

    def post(self, request, ticket_id, *args, **kwargs):
        body = ApproveRequestSerializer(data=request.data or {})
        body.is_valid(raise_exception=True)

        try:
            ticket = approve_ticket(
                ticket_id=ticket_id,
                moderator=request.user,
                comment=body.validated_data.get('comment', ''),
            )
        except TicketFlowConflict as exc:
            return self._conflict_response(exc)

        return Response(TicketResponseSerializer(ticket).data, status=status.HTTP_200_OK)


class TicketBlockAPIView(_TicketActionAPIView):
    """POST /api/v1/tickets/{ticket_id}/block — soft/hard по BlockingReason.hard_block."""

    def post(self, request, ticket_id, *args, **kwargs):
        body = BlockDecisionRequestSerializer(data=request.data or {})
        body.is_valid(raise_exception=True)

        field_reports = body.validated_data.get('field_reports') or []
        normalized_reports = [
            {
                'field_path': item['field_path'],
                'message': item['message'],
                'severity': item.get('severity', 'ERROR'),
            }
            for item in field_reports
        ]

        try:
            ticket = block_ticket(
                ticket_id=ticket_id,
                moderator=request.user,
                blocking_reason_ids=body.validated_data['blocking_reason_ids'],
                comment=body.validated_data.get('comment', ''),
                field_reports=normalized_reports,
            )
        except TicketFlowConflict as exc:
            return self._conflict_response(exc)

        return Response(TicketResponseSerializer(ticket).data, status=status.HTTP_200_OK)


class TicketReleaseAPIView(_TicketActionAPIView):
    """POST /api/v1/tickets/{ticket_id}/release."""

    def post(self, request, ticket_id, *args, **kwargs):
        try:
            ticket = release_ticket(ticket_id=ticket_id, moderator=request.user)
        except TicketFlowConflict as exc:
            return self._conflict_response(exc)

        return Response(TicketResponseSerializer(ticket).data, status=status.HTTP_200_OK)
