from django.urls import path

from .views import FavoriteDeleteView, FavoritesListView

urlpatterns = [
    path("api/v1/favorites", FavoritesListView.as_view()),
    path("api/v1/favorites/<uuid:product_id>", FavoriteDeleteView.as_view()),
]
