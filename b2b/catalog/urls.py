from django.urls import path

from .public_views import (
    PublicProductBatchAPIView,
    PublicProductListAPIView,
    PublicProductRetrieveAPIView,
    PublicProductSimilarAPIView,
    PublicSKURetrieveAPIView,
)
from .inventory_views import ReserveInventoryAPIView, UnreserveInventoryAPIView
from .moderation_events_views import ReceiveModerationEventAPIView
from .views import (
    CategoryDetailAPIView,
    CategoryListAPIView,
    ProductMyListAPIView,
    ProductListCreateAPIView,
    ProductRetrieveUpdateAPIView,
    SKUCreateAPIView,
    SKURetrieveUpdateAPIView,
)

urlpatterns = [
    path('categories/', CategoryListAPIView.as_view(), name='category-list'),
    path('categories', CategoryListAPIView.as_view(), name='category-list-no-slash'),
    path('categories/<uuid:id>', CategoryDetailAPIView.as_view(), name='category-detail-no-slash'),
    path('categories/<uuid:id>/', CategoryDetailAPIView.as_view(), name='category-detail'),
    path('public/products/', PublicProductListAPIView.as_view(), name='public-product-list'),
    path('public/products', PublicProductListAPIView.as_view(), name='public-product-list-no-slash'),
    path(
        'public/products/batch/',
        PublicProductBatchAPIView.as_view(),
        name='public-product-batch',
    ),
    path(
        'public/products/batch',
        PublicProductBatchAPIView.as_view(),
        name='public-product-batch-no-slash',
    ),
    path(
        'public/products/<uuid:product_id>/similar/',
        PublicProductSimilarAPIView.as_view(),
        name='public-product-similar',
    ),
    path(
        'public/products/<uuid:product_id>/similar',
        PublicProductSimilarAPIView.as_view(),
        name='public-product-similar-no-slash',
    ),
    path(
        'public/products/<uuid:product_id>/',
        PublicProductRetrieveAPIView.as_view(),
        name='public-product-detail',
    ),
    path(
        'public/products/<uuid:product_id>',
        PublicProductRetrieveAPIView.as_view(),
        name='public-product-detail-no-slash',
    ),
    path(
        'public/skus/<uuid:sku_id>/',
        PublicSKURetrieveAPIView.as_view(),
        name='public-sku-detail',
    ),
    path(
        'public/skus/<uuid:sku_id>',
        PublicSKURetrieveAPIView.as_view(),
        name='public-sku-detail-no-slash',
    ),
    path('products/', ProductListCreateAPIView.as_view(), name='product-list-create'),
    path('products', ProductListCreateAPIView.as_view(), name='product-list-create-no-slash'),
    path('products/my', ProductMyListAPIView.as_view(), name='product-my-list-no-slash'),
    path('products/my/', ProductMyListAPIView.as_view(), name='product-my-list'),
    # str:pk нужен для явной 400-валидации невалидного UUID в GET /products/{id}.
    path('products/<str:pk>/', ProductRetrieveUpdateAPIView.as_view(), name='product-detail'),
    path('products/<str:pk>', ProductRetrieveUpdateAPIView.as_view(), name='product-detail-no-slash'),
    path('skus/', SKUCreateAPIView.as_view(), name='sku-create'),
    path('skus', SKUCreateAPIView.as_view(), name='sku-create-no-slash'),
    path('skus/<uuid:pk>/', SKURetrieveUpdateAPIView.as_view(), name='sku-detail'),
    path('skus/<uuid:pk>', SKURetrieveUpdateAPIView.as_view(), name='sku-detail-no-slash'),
    path('inventory/reserve/', ReserveInventoryAPIView.as_view(), name='inventory-reserve'),
    path('inventory/reserve', ReserveInventoryAPIView.as_view(), name='inventory-reserve-no-slash'),
    path('inventory/unreserve/', UnreserveInventoryAPIView.as_view(), name='inventory-unreserve'),
    path('inventory/unreserve', UnreserveInventoryAPIView.as_view(), name='inventory-unreserve-no-slash'),
    path(
        'moderation/events/',
        ReceiveModerationEventAPIView.as_view(),
        name='moderation-events',
    ),
    path(
        'moderation/events',
        ReceiveModerationEventAPIView.as_view(),
        name='moderation-events-no-slash',
    ),
]
