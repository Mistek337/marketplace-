from django.urls import path

from .views import FavoriteItemView, FavoriteSubscribeView, FavoritesListView

urlpatterns = [
    path("favorites", FavoritesListView.as_view()),
    path("favorites/<uuid:product_id>", FavoriteItemView.as_view()),
    path(
        "favorites/<uuid:product_id>/subscribe",
        FavoriteSubscribeView.as_view(),
    ),
]
