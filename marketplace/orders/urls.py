from django.urls import path

from .views import OrderCancelAPIView, OrderCreateAPIView

urlpatterns = [
    path("orders", OrderCreateAPIView.as_view(), name="order-create"),
    path("orders/<uuid:order_id>/cancel", OrderCancelAPIView.as_view(), name="order-cancel"),
    path("orders/<uuid:order_id>/cancel/", OrderCancelAPIView.as_view(), name="order-cancel-slash"),
]
