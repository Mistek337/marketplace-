from django.urls import path

from .dev_views import DevSeedProductView
from .views import (
    BreadcrumbsView,
    CatalogFacetsView,
    CatalogPageView,
    CategoryFiltersView,
    CategoriesTreeView,
    ProductDetailView,
    ProductPageView,
    ProductSimilarView,
    ProductSKUsView,
    ProductSKUDetailView,
    ProductsListView,
)


urlpatterns = [
    path("catalog/", CatalogPageView.as_view(), name="catalog"),
    path(
        "products/<uuid:product_id>",
        ProductPageView.as_view(),
        name="product-page",
    ),
    # Временно: создание товара для тестов (только DEBUG=True)
    path("api/v1/dev/products", DevSeedProductView.as_view()),
    path("api/v1/categories", CategoriesTreeView.as_view()),
    path("api/v1/categories/<str:category_id>/filters", CategoryFiltersView.as_view()),
    path("api/v1/catalog/facets", CatalogFacetsView.as_view()),
    path("api/v1/breadcrumbs", BreadcrumbsView.as_view()),
    path("api/v1/products", ProductsListView.as_view()),
    path("api/v1/products/<uuid:product_id>", ProductDetailView.as_view()),
    path("api/v1/products/<uuid:product_id>/similar", ProductSimilarView.as_view()),
    path("api/v1/products/<uuid:product_id>/skus", ProductSKUsView.as_view()),
    path(
        "api/v1/products/<uuid:product_id>/skus/<uuid:sku_id>",
        ProductSKUDetailView.as_view(),
    ),
]

