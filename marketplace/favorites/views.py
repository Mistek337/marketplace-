from django.db import DatabaseError
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import ProductSubscription
from .services import (
    build_favorites_list_response,
    fetch_visible_product,
    parse_pagination,
    parse_subscribe_events,
)


class FavoritesListView(APIView):
    """GET /api/v1/favorites — PaginatedCatalogProducts."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        limit, offset = parse_pagination(request)
        return Response(build_favorites_list_response(request.user, limit=limit, offset=offset))


class FavoriteItemView(APIView):
    """PUT/DELETE /api/v1/favorites/{product_id}."""

    permission_classes = [permissions.IsAuthenticated]

    def put(self, request, product_id):
        _, error = fetch_visible_product(product_id)
        if error is not None:
            return error

        try:
            request.user.favorites.get_or_create(product_id=product_id)
        except DatabaseError:
            pass

        return Response(status=status.HTTP_204_NO_CONTENT)

    def delete(self, request, product_id):
        request.user.favorites.filter(product_id=product_id).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class FavoriteSubscribeView(APIView):
    """POST/DELETE /api/v1/favorites/{product_id}/subscribe."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, product_id):
        _, error = fetch_visible_product(product_id)
        if error is not None:
            return error

        events = parse_subscribe_events(request)
        ProductSubscription.objects.update_or_create(
            user=request.user,
            product_id=product_id,
            defaults={"events": events},
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

    def delete(self, request, product_id):
        request.user.product_subscriptions.filter(product_id=product_id).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
