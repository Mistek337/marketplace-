"""Мягкое удаление товара (OpenAPI DELETE /api/v1/products/{product_id})."""

from __future__ import annotations

import uuid
from uuid import UUID

from django.db import transaction

from .models import Product


class DeleteProductError(Exception):
    def __init__(self, *, code: str, message: str, status_code: int = 400):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def delete_product(*, seller_id: UUID, product_id: UUID) -> None:
    """
    deleted=true, события DELETED → Moderation и PRODUCT_DELETED → B2C.
    OpenAPI deleteProduct: 204 / 403 (чужой) / 404 (нет или уже удалён).
    """
    product = Product.objects.prefetch_related("skus").filter(pk=product_id).first()
    if product is None:
        raise DeleteProductError(
            code="NOT_FOUND",
            message="Product not found",
            status_code=404,
        )

    if product.seller_id != seller_id:
        raise DeleteProductError(
            code="NOT_OWNER",
            message="Product does not belong to the authenticated seller",
            status_code=403,
        )

    if product.deleted:
        raise DeleteProductError(
            code="NOT_FOUND",
            message="Product not found",
            status_code=404,
        )

    sku_ids = [sku.id for sku in product.skus.all()]

    with transaction.atomic():
        locked = Product.objects.select_for_update().get(pk=product.pk)
        if locked.deleted:
            raise DeleteProductError(
                code="NOT_FOUND",
                message="Product not found",
                status_code=404,
            )
        locked.deleted = True
        locked.save(update_fields=["deleted", "updated_at"])

    from .b2c_client import emit_product_deleted_event
    from .moderation_client import emit_product_deleted_to_moderation

    emit_product_deleted_to_moderation(product_id=product_id, seller_id=product.seller_id)
    emit_product_deleted_event(product_id=product_id, sku_ids=sku_ids)
