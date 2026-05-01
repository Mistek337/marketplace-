"""REST API B2C под префиксом /api/v1/ (подключается из marketplace.urls)."""

from django.urls import path

from .dev_views import DevSeedProductView
from .views import (
    BreadcrumbsView,
    CatalogFacetsView,
    CategoryFiltersView,
    CategoriesTreeView,
    ProductDetailView,
    ProductSimilarView,
    ProductSKUsView,
    ProductSKUDetailView,
    ProductsListView,
)

urlpatterns = [
    path("dev/products", DevSeedProductView.as_view()),
    path("categories", CategoriesTreeView.as_view()),
    path("categories/<str:category_id>/filters", CategoryFiltersView.as_view()),
    path("catalog/facets", CatalogFacetsView.as_view()),
    path("breadcrumbs", BreadcrumbsView.as_view()),
    path("products", ProductsListView.as_view()),
    path("products/<uuid:product_id>", ProductDetailView.as_view()),
    path("products/<uuid:product_id>/similar", ProductSimilarView.as_view()),
    path("products/<uuid:product_id>/skus", ProductSKUsView.as_view()),
    path(
        "products/<uuid:product_id>/skus/<uuid:sku_id>",
        ProductSKUDetailView.as_view(),
    ),
]
