from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Invoice
from .serializers import InvoiceAcceptSerializer, InvoiceCreateSerializer


class InvoiceCreateAPIView(generics.CreateAPIView):
    """POST /api/v1/invoices — создать накладную (статус CREATED, склад ещё не принял)."""

    queryset = Invoice.objects.all()
    serializer_class = InvoiceCreateSerializer


class InvoiceAcceptAPIView(APIView):
    """POST /api/v1/invoices/accept — принять накладную на склад (остатки SKU + статус ACCEPTED)."""

    def post(self, request, *args, **kwargs):
        serializer = InvoiceAcceptSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)
