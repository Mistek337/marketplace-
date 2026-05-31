from django.urls import path

from .views import TicketApproveAPIView

urlpatterns = [
    path(
        'tickets/<uuid:ticket_id>/approve/',
        TicketApproveAPIView.as_view(),
        name='ticket-approve',
    ),
    path(
        'tickets/<uuid:ticket_id>/approve',
        TicketApproveAPIView.as_view(),
        name='ticket-approve-no-slash',
    ),
]
