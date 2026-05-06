from django.urls import path

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
]
