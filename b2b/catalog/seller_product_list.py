"""Queryset для GET /api/v1/products — кабинет продавца (OpenAPI listMyProducts)."""

from __future__ import annotations

from uuid import UUID

from django.db.models import Count, IntegerField, Min, Sum, Value
from django.db.models.functions import Coalesce

from .models import Product


def seller_product_list_queryset(
    *,
    seller_id: UUID,
    include_deleted: bool = False,
    status: str | None = None,
    search: str | None = None,
):
    """
    seller_id только из JWT — query-параметр seller_id игнорируется на уровне view.
    Аннотации skus_count / total_active_quantity / min_price — один SQL без N+1.
    """
    qs = (
        Product.objects.filter(seller_id=seller_id)
        .prefetch_related("image_rows")
        .annotate(
            skus_count=Count("skus", distinct=True),
            total_active_quantity=Coalesce(
                Sum("skus__active_quantity"),
                Value(0),
                output_field=IntegerField(),
            ),
            min_price=Min("skus__price"),
        )
        .order_by("-created_at")
    )

    if not include_deleted:
        qs = qs.filter(deleted=False)

    if status:
        qs = qs.filter(status=status)

    if search:
        qs = qs.filter(title__icontains=search)

    return qs
