import uuid

from django.db import DatabaseError
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from catalog.b2b_client import B2BClient, B2BClientError


def _safe_sku_qty(first):
    if not isinstance(first, dict):
        return 0
    q = first.get("active_quantity")
    if q is None:
        q = first.get("activeQuantity")
    try:
        return int(q) if q is not None else 0
    except (TypeError, ValueError):
        return 0


def _b2c_product_stub(product_id, raw):
    if not isinstance(raw, dict):
        return {"product_id": str(product_id), "title": None, "error": "invalid_upstream"}
    skus = raw.get("skus") or []
    first = skus[0] if skus and isinstance(skus[0], dict) else {}
    qty = _safe_sku_qty(first)
    price = first.get("price")
    if price is not None:
        try:
            price = int(price)
        except (TypeError, ValueError):
            price = None
    return {
        "product_id": str(product_id),
        "title": raw.get("title"),
        "price": price,
        "in_stock": qty > 0,
    }


class FavoritesListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        rows = request.user.favorites.all()
        client = B2BClient()
        items = []
        for row in rows:
            try:
                p = client.get_product(row.product_id)
            except B2BClientError:
                continue
            items.append(_b2c_product_stub(row.product_id, p))
        return Response({"items": items})

    def post(self, request):
        raw = request.data.get("product_id")
        try:
            product_id = uuid.UUID(str(raw))
        except (ValueError, TypeError):
            return Response(
                {"code": "INVALID_REQUEST", "message": "product_id must be a valid UUID"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            fav, _ = request.user.favorites.get_or_create(product_id=product_id)
        except DatabaseError as exc:
            return Response(
                {
                    "code": "DATABASE_ERROR",
                    "message": "Выполните миграции B2C: python manage.py migrate",
                    "detail": str(exc),
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        client = B2BClient()
        try:
            p = client.get_product(fav.product_id)
        except B2BClientError as exc:
            if exc.status_code == 404:
                return Response(
                    {"code": "NOT_FOUND", "message": "Product not found"},
                    status=status.HTTP_404_NOT_FOUND,
                )
            return Response(
                {"message": "Catalog service error"},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        return Response(_b2c_product_stub(fav.product_id, p), status=status.HTTP_201_CREATED)


class FavoriteDeleteView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request, product_id):
        deleted, _ = request.user.favorites.filter(product_id=product_id).delete()
        if not deleted:
            return Response(status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_204_NO_CONTENT)
