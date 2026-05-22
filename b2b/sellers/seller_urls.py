from django.urls import path

from .views import SellerMeAPIView


urlpatterns = [
    path("me", SellerMeAPIView.as_view(), name="seller-me"),
    path("me/", SellerMeAPIView.as_view(), name="seller-me-slash"),
]
