from rest_framework import generics, permissions, status
from rest_framework.response import Response

from catalog.api_errors import UNAUTHORIZED, drf_validation_error, error_body
from sellers.auth import SellerJWTAuthentication

from .invoice_create_service import CreateInvoiceError, create_invoice
from .serializers import InvoiceCreateSerializer, InvoiceResponseSerializer


class InvoiceCreateAPIView(generics.GenericAPIView):
    """POST /api/v1/invoices — OpenAPI createInvoice."""

    authentication_classes = [SellerJWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = InvoiceCreateSerializer

    def post(self, request, *args, **kwargs):
        if not request.user or not getattr(request.user, "is_authenticated", False):
            return Response(
                error_body(code=UNAUTHORIZED, message="Authentication required"),
                status=status.HTTP_401_UNAUTHORIZED,
            )

        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                drf_validation_error(serializer.errors),
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        items = serializer.validated_data["items"]
        if not items:
            return Response(
                error_body(
                    code="VALIDATION_ERROR",
                    message="Invoice must contain at least one item",
                ),
                status=status.HTTP_400_BAD_REQUEST,
            )

        seller_id = getattr(request.user, "id", None)
        try:
            invoice = create_invoice(
                seller_id=seller_id,
                items=[
                    {"sku_id": row["sku_id"], "quantity": row["quantity"]}
                    for row in items
                ],
            )
        except CreateInvoiceError as exc:
            return Response(
                error_body(code=exc.code, message=exc.message),
                status=exc.status_code,
            )

        return Response(
            InvoiceResponseSerializer(invoice).data,
            status=status.HTTP_201_CREATED,
        )
