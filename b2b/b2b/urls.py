"""
URL configuration for b2b project.
"""
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/auth/', include('sellers.urls')),
    path('api/v1/seller/', include('sellers.seller_urls')),
    path('api/v1/', include('catalog.urls')),
    path('api/v1/', include('invoices.urls')),
]
