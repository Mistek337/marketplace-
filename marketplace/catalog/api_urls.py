"""REST API B2C: только эндпоинты OpenAPI (тег Catalog)."""

from django.urls import path

from .catalog_openapi_views import (
    CatalogBannersView,
    CatalogCategoriesListView,
    CatalogCategoriesTreeView,
    CatalogCollectionsView,
    CatalogProductSimilarView,
    CatalogProductsListView,
)
from .views import ProductDetailView

urlpatterns = [
    path("catalog/categories", CatalogCategoriesListView.as_view()),
    path("catalog/categories/tree", CatalogCategoriesTreeView.as_view()),
    path("catalog/products", CatalogProductsListView.as_view()),
    path("catalog/products/<uuid:product_id>", ProductDetailView.as_view()),
    path(
        "catalog/products/<uuid:product_id>/similar",
        CatalogProductSimilarView.as_view(),
    ),
    path("catalog/banners", CatalogBannersView.as_view()),
    path("catalog/collections", CatalogCollectionsView.as_view()),
]
