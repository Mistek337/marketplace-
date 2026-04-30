from django.urls import path

from .views import InvoiceAcceptAPIView, InvoiceCreateAPIView

urlpatterns = [
    path('invoices/', InvoiceCreateAPIView.as_view(), name='invoice-create'),
    path('invoices', InvoiceCreateAPIView.as_view(), name='invoice-create-no-slash'),
    path('invoices/accept/', InvoiceAcceptAPIView.as_view(), name='invoice-accept'),
    path('invoices/accept', InvoiceAcceptAPIView.as_view(), name='invoice-accept-no-slash'),
]
