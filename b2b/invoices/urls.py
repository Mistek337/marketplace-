from django.urls import path

from .views import InvoiceCreateAPIView

urlpatterns = [
    path("invoices/", InvoiceCreateAPIView.as_view(), name="invoice-create"),
    path("invoices", InvoiceCreateAPIView.as_view(), name="invoice-create-no-slash"),
]
