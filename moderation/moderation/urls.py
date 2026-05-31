"""
URL configuration for moderation project.
"""
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/auth/', include('tickets.auth_urls')),
    path('api/v1/', include('events.urls')),
    path('api/v1/', include('tickets.urls')),
]
