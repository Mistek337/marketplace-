from django.urls import path

from .views import (
    CartAPIView,
    CartItemDetailAPIView,
    CartItemsAPIView,
    CartMergeAPIView,
    CartValidateAPIView,
)

urlpatterns = [
    path("cart", CartAPIView.as_view(), name="cart"),
    path("cart/", CartAPIView.as_view(), name="cart-slash"),
    path("cart/items", CartItemsAPIView.as_view(), name="cart-items"),
    path("cart/items/", CartItemsAPIView.as_view(), name="cart-items-slash"),
    path("cart/items/<uuid:sku_id>", CartItemDetailAPIView.as_view(), name="cart-item-detail"),
    path("cart/items/<uuid:sku_id>/", CartItemDetailAPIView.as_view(), name="cart-item-detail-slash"),
    path("cart/merge", CartMergeAPIView.as_view(), name="cart-merge"),
    path("cart/merge/", CartMergeAPIView.as_view(), name="cart-merge-slash"),
    path("cart/validate", CartValidateAPIView.as_view(), name="cart-validate"),
    path("cart/validate/", CartValidateAPIView.as_view(), name="cart-validate-slash"),
]
