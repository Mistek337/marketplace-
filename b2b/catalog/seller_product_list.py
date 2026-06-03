"""Queryset для GET /api/v1/products — OpenAPI listMyProducts."""

from __future__ import annotations

from uuid import UUID

from django.db.models import Min

from .models import Product


def seller_product_list_queryset(
    *,
    seller_id: UUID,
    include_deleted: bool = False,
    status: str | None = None,
):
    """seller_id только из JWT; query seller_id игнорируется во view."""
    qs = (
        Product.objects.filter(seller_id=seller_id)
        .prefetch_related("image_rows")
        .annotate(min_price=Min("skus__price"))
        .order_by("-created_at")
    )

    if not include_deleted:
        qs = qs.filter(deleted=False)

    if status:
        qs = qs.filter(status=status)

    return qs
