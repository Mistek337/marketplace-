from django.urls import path

from .views import FavoriteDeleteView, FavoritesListView

urlpatterns = [
    path("favorites", FavoritesListView.as_view()),
    path("favorites/<uuid:product_id>", FavoriteDeleteView.as_view()),
]
