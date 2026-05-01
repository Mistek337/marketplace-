"""Публичные HTML-страницы каталога (без префикса /api/v1/)."""

from django.urls import path

from .views import CatalogPageView, ProductPageView

urlpatterns = [
    path("catalog/", CatalogPageView.as_view(), name="catalog"),
    path(
        "products/<uuid:product_id>",
        ProductPageView.as_view(),
        name="product-page",
    ),
]
