import uuid

from django.db import DatabaseError
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from catalog.b2b_client import B2BClient, B2BClientError


def _parse_pagination(request):
    try:
        limit = int(request.query_params.get("limit", 20))
        offset = int(request.query_params.get("offset", 0))
    except ValueError:
        return None, None
    limit = max(1, min(limit, 100))
    offset = max(0, offset)
    return limit, offset


def _to_favorite_item(product: dict) -> dict:
    """
    B2B отдаёт структуру товара с `skus`/`images`. Для избранного нам достаточно
    компактной карточки; скрытые SKU-поля всё равно фильтруются на стороне B2C catalog.
    """
    skus = product.get("skus") or []
    first = skus[0] if skus and isinstance(skus[0], dict) else {}
    qty = first.get("active_quantity")
    if qty is None:
        qty = first.get("activeQuantity", 0)
    try:
        qty = int(qty or 0)
    except (TypeError, ValueError):
        qty = 0

    price = first.get("price")
    try:
        price = int(price) if price is not None else None
    except (TypeError, ValueError):
        price = None

    images = product.get("images") or []
    image = images[0].get("url") if images and isinstance(images[0], dict) else None
    return {
        "product_id": str(product.get("id")),
        "title": product.get("title"),
        "image": image,
        "price": price,
        "in_stock": qty > 0,
    }


class FavoritesListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        # IDOR защита: user_id берём только из JWT (request.user), query игнорируем.
        limit, offset = _parse_pagination(request)
        if limit is None:
            return Response(
                {"code": "INVALID_REQUEST", "message": "Invalid pagination parameters"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        base_qs = request.user.favorites.all()
        total = base_qs.count()
        rows = list(base_qs[offset : offset + limit])
        if not rows:
            return Response({"items": [], "total": total, "limit": limit, "offset": offset})

        ids = ",".join(str(r.product_id) for r in rows)
        client = B2BClient()
        try:
            data = client.get_products(limit=len(rows), offset=0, ids=ids)
        except B2BClientError:
            return Response(
                {"code": "B2B_UNAVAILABLE", "message": "Catalog service unavailable"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        pool = data.get("items", []) if isinstance(data, dict) else []
        items = [_to_favorite_item(p) for p in pool if isinstance(p, dict) and p.get("id")]
        return Response({"items": items, "total": total, "limit": limit, "offset": offset})


class FavoriteItemView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, product_id):
        # SECURITY: user_id только из JWT (request.user). Любые user_id в query/body игнорируем.
        client = B2BClient()
        try:
            product = client.get_product(product_id)
        except B2BClientError as exc:
            if exc.status_code == 404:
                return Response(
                    {"code": "NOT_FOUND", "message": "Product not found"},
                    status=status.HTTP_404_NOT_FOUND,
                )
            return Response(
                {"code": "B2B_UNAVAILABLE", "message": "Catalog service unavailable"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        try:
            fav, created = request.user.favorites.get_or_create(product_id=product_id)
        except DatabaseError as exc:
            return Response(
                {
                    "code": "DATABASE_ERROR",
                    "message": "Выполните миграции B2C: python manage.py migrate",
                    "detail": str(exc),
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        payload = _to_favorite_item(product) if isinstance(product, dict) else {"product_id": str(product_id)}
        payload["added_at"] = fav.added_at.isoformat().replace("+00:00", "Z")
        return Response(payload, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

    def delete(self, request, product_id):
        # Идемпотентно: даже если записи нет — считаем удалённой.
        request.user.favorites.filter(product_id=product_id).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
