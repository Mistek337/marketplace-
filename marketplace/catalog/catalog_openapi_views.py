"""Catalog API — эндпоинты OpenAPI (тег Catalog)."""

from django.conf import settings
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .b2b_client import B2BClient, B2BClientError
from .openapi_catalog import (
    categories_to_refs,
    to_catalog_product_card,
    to_catalog_product_detail,
    to_category_tree_nodes,
)
from .request_parsing import parse_catalog_list_params, parse_similar_limit_param
from .api_errors import map_b2b_error


def _validation_error(message: str, *, status_code=status.HTTP_400_BAD_REQUEST):
    return Response(
        {"code": "VALIDATION_ERROR", "message": message},
        status=status_code,
    )


def _load_categories(client: B2BClient):
    try:
        return client.get_categories()
    except B2BClientError:
        return []


def _is_visible_product(product: dict) -> bool:
    if getattr(settings, "CATALOG_DEV_VISIBILITY", False):
        return not bool(product.get("deleted", False))
    return product.get("status") == "MODERATED" and not bool(product.get("deleted", False))


def catalog_products_list(request):
    """Общая логика GET листинга → PaginatedCatalogProducts."""
    params, err = parse_catalog_list_params(request)
    if err:
        return _validation_error(err)

    client = B2BClient()
    try:
        data = client.get_products(
            limit=params["limit"],
            offset=params["offset"],
            category_id=params.get("category_id"),
            seller_id=params.get("seller_id"),
            min_price=params.get("min_price"),
            max_price=params.get("max_price"),
            char_filters=params.get("char_filters"),
            sort=params.get("sort"),
            search=params.get("search"),
        )
    except B2BClientError as exc:
        if exc.status_code == 422:
            return _validation_error("Invalid catalog filters", status_code=422)
        return map_b2b_error(exc)

    categories = _load_categories(client)
    raw_items = data.get("items", []) if isinstance(data, dict) else []
    items = []
    for row in raw_items:
        if not isinstance(row, dict) or not _is_visible_product(row):
            continue
        items.append(to_catalog_product_card(row, categories_flat=categories))

    return Response(
        {
            "items": items,
            "total_count": int(data.get("total_count", len(items))),
            "limit": params["limit"],
            "offset": params["offset"],
        }
    )


class CatalogProductsListView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        return catalog_products_list(request)


class CatalogCategoriesListView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        client = B2BClient()
        try:
            categories = client.get_categories()
        except B2BClientError as exc:
            return map_b2b_error(exc)
        return Response(categories_to_refs(categories))


class CatalogCategoriesTreeView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        client = B2BClient()
        try:
            categories = client.get_categories()
        except B2BClientError as exc:
            return map_b2b_error(exc)
        return Response(to_category_tree_nodes(categories))


class CatalogProductSimilarView(APIView):
    """GET /api/v1/catalog/products/{product_id}/similar — OpenAPI: только 200 + [CatalogProductCard]."""

    permission_classes = [permissions.AllowAny]

    def get(self, request, product_id):
        limit = parse_similar_limit_param(request)
        client = B2BClient()
        try:
            pool = client.get_similar_products(product_id, limit=limit)
        except B2BClientError:
            pool = []

        if not isinstance(pool, list):
            pool = []

        cards = [
            to_catalog_product_card(row)
            for row in pool
            if isinstance(row, dict)
        ]
        return Response(cards)


class CatalogBannersView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        return Response([])


class CatalogCollectionsView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        return Response([])
