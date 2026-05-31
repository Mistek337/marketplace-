from django.urls import path

from .views import B2BEventsAPIView, HealthAPIView

urlpatterns = [
    path('health/', HealthAPIView.as_view(), name='health'),
    path('health', HealthAPIView.as_view(), name='health-no-slash'),
    path('b2b/events/', B2BEventsAPIView.as_view(), name='b2b-events'),
    path('b2b/events', B2BEventsAPIView.as_view(), name='b2b-events-no-slash'),
]
