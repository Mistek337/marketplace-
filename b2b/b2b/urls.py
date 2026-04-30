"""
URL configuration for b2b project.
"""
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/auth/', include('sellers.urls')),
    path('api/seller/', include('sellers.seller_urls')),
    path('api/', include('catalog.urls')),
    path('api/', include('invoices.urls')),
]
