"""Удаление SKU (OpenAPI DELETE /api/v1/skus/{sku_id})."""

from __future__ import annotations

from uuid import UUID

from django.db import transaction

from .api_errors import CONFLICT
from .models import Product, SKU


class DeleteSKUError(Exception):
    def __init__(self, *, code: str, message: str, status_code: int = 400):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def delete_sku(*, sku_id: UUID) -> None:
    """
    Физическое удаление SKU.

    OpenAPI deleteSku: 204 / 409 (reserved_quantity > 0).
    Side-эффекты по канон-flow: SKU_OUT_OF_STOCK, last SKU → CREATED + DELETED.
    """
    sku = SKU.objects.select_related("product").filter(pk=sku_id).first()
    if sku is None:
        return

    product = sku.product

    if sku.reserved_quantity > 0:
        raise DeleteSKUError(
            code=CONFLICT,
            message="SKU has active reservations",
            status_code=409,
        )

    emit_out_of_stock = (
        product.status == Product.Status.MODERATED and sku.active_quantity > 0
    )
    captured_sku_id = sku.id
    captured_product_id = product.id
    captured_seller_id = product.seller_id

    with transaction.atomic():
        sku = SKU.objects.select_for_update().select_related("product").filter(pk=sku_id).first()
        if sku is None:
            return

        product = Product.objects.select_for_update().get(pk=sku.product_id)

        if sku.reserved_quantity > 0:
            raise DeleteSKUError(
                code=CONFLICT,
                message="SKU has active reservations",
                status_code=409,
            )

        sku.delete()

        emit_moderation_deleted = (
            product.status == Product.Status.ON_MODERATION
            and not product.skus.exists()
        )
        if emit_moderation_deleted:
            product.status = Product.Status.CREATED
            product.save(update_fields=["status", "updated_at"])

    from .b2c_client import emit_sku_out_of_stock_event
    from .moderation_client import emit_product_deleted_to_moderation

    if emit_out_of_stock:
        emit_sku_out_of_stock_event(
            sku_id=captured_sku_id,
            product_id=captured_product_id,
        )

    if emit_moderation_deleted:
        emit_product_deleted_to_moderation(
            product_id=captured_product_id,
            seller_id=captured_seller_id,
        )
