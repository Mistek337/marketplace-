from django.urls import path

from .views import SellerProfileDeleteView, SellerProfileUpdateView, SellerProfileView


urlpatterns = [
    path("profile", SellerProfileView.as_view(), name="seller-profile"),
    path("profile/update", SellerProfileUpdateView.as_view(), name="seller-profile-update"),
    path("profile/delete", SellerProfileDeleteView.as_view(), name="seller-profile-delete"),
]
