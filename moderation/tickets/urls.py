from django.urls import path

from .views import TicketApproveAPIView, TicketBlockAPIView, TicketReleaseAPIView

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
    path(
        'tickets/<uuid:ticket_id>/block/',
        TicketBlockAPIView.as_view(),
        name='ticket-block',
    ),
    path(
        'tickets/<uuid:ticket_id>/block',
        TicketBlockAPIView.as_view(),
        name='ticket-block-no-slash',
    ),
    path(
        'tickets/<uuid:ticket_id>/release/',
        TicketReleaseAPIView.as_view(),
        name='ticket-release',
    ),
    path(
        'tickets/<uuid:ticket_id>/release',
        TicketReleaseAPIView.as_view(),
        name='ticket-release-no-slash',
    ),
]
