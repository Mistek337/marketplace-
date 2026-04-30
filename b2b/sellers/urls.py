from django.urls import path

from .views import (
    SellerLoginView,
    SellerLogoutView,
    SellerRefreshView,
    SellerRegisterView,
)


urlpatterns = [
    path("register", SellerRegisterView.as_view(), name="seller-register"),
    path("login", SellerLoginView.as_view(), name="seller-login"),
    path("refresh", SellerRefreshView.as_view(), name="seller-refresh"),
    path("logout", SellerLogoutView.as_view(), name="seller-logout"),
]
