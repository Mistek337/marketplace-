from uuid import UUID

from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .api_errors import error_body, service_unavailable
from .responses import order_to_response
from .serializers import OrderCreateRequestSerializer
from .services import CheckoutError, checkout_order


def _parse_idempotency_key(request) -> UUID | None:
    raw = request.headers.get("Idempotency-Key") or request.META.get("HTTP_IDEMPOTENCY_KEY")
    if not raw:
        return None
    try:
        return UUID(str(raw))
    except (TypeError, ValueError):
        return None


class OrderCreateAPIView(APIView):
    """POST /api/v1/orders — checkout (OpenAPI)."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        idempotency_key = _parse_idempotency_key(request)
        if idempotency_key is None:
            return Response(
                error_body(
                    code="VALIDATION_ERROR",
                    message="Idempotency-Key header is required and must be a UUID",
                ),
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = OrderCreateRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                error_body(
                    code="VALIDATION_ERROR",
                    message="Invalid order data",
                    details=serializer.errors,
                ),
                status=status.HTTP_400_BAD_REQUEST,
            )

        body = serializer.validated_data
        try:
            order, created = checkout_order(
                buyer=request.user,
                idempotency_key=idempotency_key,
                body=body,
            )
        except CheckoutError as exc:
            if exc.status_code == 422 and exc.details and "validation" in exc.details:
                return Response(
                    exc.details["validation"],
                    status=status.HTTP_422_UNPROCESSABLE_ENTITY,
                )
            if exc.status_code == 503:
                return service_unavailable(exc.message)
            return Response(
                error_body(code=exc.code, message=exc.message, details=exc.details),
                status=exc.status_code,
            )

        response_status = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        return Response(order_to_response(order), status=response_status)
