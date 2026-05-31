from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from events.api_errors import CONFLICT, error_body
from tickets.authentication import ModeratorHeaderAuthentication
from tickets.serializers import ApproveRequestSerializer, TicketResponseSerializer
from tickets.services import ApproveConflict, approve_ticket


class TicketApproveAPIView(APIView):
    """POST /api/v1/tickets/{ticket_id}/approve — IN_REVIEW → APPROVED + событие MODERATED в B2B."""

    authentication_classes = [ModeratorHeaderAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, ticket_id, *args, **kwargs):
        body = ApproveRequestSerializer(data=request.data or {})
        body.is_valid(raise_exception=True)

        try:
            ticket = approve_ticket(
                ticket_id=ticket_id,
                moderator=request.user,
                comment=body.validated_data.get('comment', ''),
            )
        except ApproveConflict as exc:
            return Response(
                error_body(code=exc.code, message=exc.message),
                status=status.HTTP_409_CONFLICT,
            )

        return Response(
            TicketResponseSerializer(ticket).data,
            status=status.HTTP_200_OK,
        )
