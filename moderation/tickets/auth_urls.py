from django.urls import path

from tickets.auth_views import LoginAPIView, LogoutAPIView, RefreshAPIView

urlpatterns = [
    path('login/', LoginAPIView.as_view(), name='auth-login'),
    path('login', LoginAPIView.as_view(), name='auth-login-no-slash'),
    path('refresh/', RefreshAPIView.as_view(), name='auth-refresh'),
    path('refresh', RefreshAPIView.as_view(), name='auth-refresh-no-slash'),
    path('logout/', LogoutAPIView.as_view(), name='auth-logout'),
    path('logout', LogoutAPIView.as_view(), name='auth-logout-no-slash'),
]
