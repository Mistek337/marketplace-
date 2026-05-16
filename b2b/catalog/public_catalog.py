"""Витринный каталог B2C → B2B (OpenAPI /api/v1/public/products)."""

from __future__ import annotations

import re
from uuid import UUID

from django.conf import settings
from django.db.models import Exists, Min, OuterRef, Prefetch, Q, QuerySet
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response

from .api_errors import UNAUTHORIZED, drf_validation_error, error_body
from .models import Product, ProductCharacteristic, ProductImage, SKU

_FILTER_KEY_RE = re.compile(r"^filters\[(.+)\]$")
PUBLIC_SORT_VALUES = frozenset({"price_asc", "price_desc", "created_desc", "popular"})


def require_b2c_service_key(request: Request) -> Response | None:
    service_key = request.headers.get("X-Service-Key")
    expected = getattr(settings, "B2C_TO_B2B_KEY", "") or ""
    if not expected or service_key != expected:
        return Response(
            error_body(code=UNAUTHORIZED, message="Missing or invalid X-Service-Key"),
            status=status.HTTP_401_UNAUTHORIZED,
        )
    return None


def _parse_optional_uuid(
    param_name: str,
    raw: str | None,
) -> tuple[UUID | None, Response | None]:
    if raw is None or raw == "":
        return None, None
    try:
        return UUID(str(raw)), None
    except (TypeError, ValueError):
        return None, Response(
            drf_validation_error({param_name: "Must be a valid UUID."}),
            status=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )


def parse_pagination(request: Request) -> tuple[int, int] | Response:
    try:
        limit = int(request.query_params.get("limit", 20))
        offset = int(request.query_params.get("offset", 0))
    except (TypeError, ValueError):
        return Response(
            drf_validation_error({"limit": "Invalid pagination parameters"}),
            status=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )
    return max(1, min(limit, 100)), max(0, offset)


def public_visible_queryset(*, with_stock_filter: bool = True) -> QuerySet[Product]:
    qs = Product.objects.select_related("category").prefetch_related(
        Prefetch(
            "image_rows",
            queryset=ProductImage.objects.order_by("ordering", "id"),
        ),
    )

    if getattr(settings, "CATALOG_DEV_VISIBILITY", False):
        return qs.filter(deleted=False)

    if with_stock_filter:
        visible_sku_qs = SKU.objects.filter(
            product_id=OuterRef("pk"),
            active_quantity__gt=0,
        )
        qs = qs.annotate(has_stock=Exists(visible_sku_qs)).filter(
            status=Product.Status.MODERATED,
            deleted=False,
            has_stock=True,
        )
    else:
        qs = qs.filter(
            status=Product.Status.MODERATED,
            deleted=False,
        )
    return qs


def _visible_skus_queryset() -> QuerySet[SKU]:
    qs = SKU.objects.prefetch_related("characteristic_rows", "image_rows").order_by("id")
    if not getattr(settings, "CATALOG_DEV_VISIBILITY", False):
        qs = qs.filter(active_quantity__gt=0)
    return qs


def public_detail_queryset() -> QuerySet[Product]:
    return public_visible_queryset(with_stock_filter=True).prefetch_related(
        Prefetch(
            "characteristic_rows",
            queryset=ProductCharacteristic.objects.order_by("id"),
        ),
        Prefetch("skus", queryset=_visible_skus_queryset()),
    )


def apply_public_list_filters(qs: QuerySet[Product], request: Request) -> QuerySet[Product] | Response:
    search = request.query_params.get("search")
    if search is not None and search != "":
        if len(search) < 3:
            return Response(
                drf_validation_error(
                    {"search": "Ensure this field has at least 3 characters."}
                ),
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        qs = qs.filter(Q(title__icontains=search) | Q(description__icontains=search))

    category_id_raw = request.query_params.get("category_id")
    category_id, err = _parse_optional_uuid("category_id", category_id_raw)
    if err is not None:
        return err
    if category_id is not None:
        qs = qs.filter(category_id=category_id)

    seller_id_raw = request.query_params.get("seller_id")
    seller_id, err = _parse_optional_uuid("seller_id", seller_id_raw)
    if err is not None:
        return err
    if seller_id is not None:
        qs = qs.filter(seller_id=seller_id)

    qs = qs.annotate(min_price=Min("skus__price"))

    min_price = request.query_params.get("min_price")
    max_price = request.query_params.get("max_price")
    if min_price is not None or max_price is not None:
        if min_price is not None:
            try:
                qs = qs.filter(min_price__gte=int(min_price))
            except (TypeError, ValueError):
                return Response(
                    drf_validation_error({"min_price": "A valid integer is required."}),
                    status=status.HTTP_422_UNPROCESSABLE_ENTITY,
                )
        if max_price is not None:
            try:
                qs = qs.filter(min_price__lte=int(max_price))
            except (TypeError, ValueError):
                return Response(
                    drf_validation_error({"max_price": "A valid integer is required."}),
                    status=status.HTTP_422_UNPROCESSABLE_ENTITY,
                )

    for key, values in request.query_params.lists():
        match = _FILTER_KEY_RE.match(key)
        if not match:
            continue
        name = match.group(1)
        if not name:
            continue
        flat = [v for v in values if v is not None and str(v) != ""]
        if not flat:
            continue
        qs = qs.filter(
            characteristic_rows__name=name,
            characteristic_rows__value__in=flat,
        ).distinct()

    sort = request.query_params.get("sort")
    if sort is None or sort == "":
        sort = "created_desc"
    elif sort not in PUBLIC_SORT_VALUES:
        return Response(
            drf_validation_error(
                {
                    "sort": (
                        "Must be one of: price_asc, price_desc, created_desc, popular."
                    )
                }
            ),
            status=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    if sort == "price_asc":
        qs = qs.order_by("min_price")
    elif sort == "price_desc":
        qs = qs.order_by("-min_price")
    else:
        qs = qs.order_by("-created_at")

    return qs


def public_list_queryset(request: Request) -> QuerySet[Product] | Response:
    qs = public_visible_queryset(with_stock_filter=True)
    return apply_public_list_filters(qs, request)


def parse_similar_limit(request: Request) -> int | Response:
    try:
        limit = int(request.query_params.get("limit", 10))
    except (TypeError, ValueError):
        return Response(
            drf_validation_error({"limit": "A valid integer is required."}),
            status=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )
    return max(1, min(limit, 50))


def public_similar_queryset(*, product_id, limit: int) -> QuerySet[Product] | None:
    anchor = public_visible_queryset(with_stock_filter=True).filter(id=product_id).first()
    if anchor is None:
        return None
    return (
        public_visible_queryset(with_stock_filter=True)
        .filter(category_id=anchor.category_id)
        .exclude(id=product_id)
        .annotate(min_price=Min("skus__price"))
        .order_by("?")[:limit]
    )


def public_visible_sku_queryset() -> QuerySet[SKU]:
    qs = SKU.objects.select_related("product").prefetch_related(
        "characteristic_rows",
        "image_rows",
    )
    if getattr(settings, "CATALOG_DEV_VISIBILITY", False):
        return qs.filter(product__deleted=False)
    return qs.filter(
        product__status=Product.Status.MODERATED,
        product__deleted=False,
        active_quantity__gt=0,
    )

