"""Создание накладной (OpenAPI POST /api/v1/invoices, createInvoice)."""

from __future__ import annotations

from uuid import UUID

from django.db import transaction

from catalog.api_errors import NOT_OWNER, VALIDATION_ERROR
from catalog.models import Product, SKU

from .models import Invoice, InvoiceItem


class CreateInvoiceError(Exception):
    def __init__(self, *, code: str, message: str, status_code: int = 400):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def create_invoice(*, seller_id: UUID, items: list[dict]) -> Invoice:
    """
    items: [{"sku_id": UUID, "quantity": int}, ...]
    OpenAPI: статус CREATED, accepted_quantity=0 на позициях.
    """
    if not items:
        raise CreateInvoiceError(
            code=VALIDATION_ERROR,
            message="Invoice must contain at least one item",
            status_code=400,
        )

    sku_ids = [row["sku_id"] for row in items]
    skus = {
        sku.id: sku
        for sku in SKU.objects.select_related("product").filter(id__in=sku_ids)
    }

    if len(skus) != len(set(sku_ids)):
        raise CreateInvoiceError(
            code=VALIDATION_ERROR,
            message="One or more SKU not found",
            status_code=400,
        )

    for row in items:
        sku = skus[row["sku_id"]]
        product = sku.product

        if product.seller_id != seller_id:
            raise CreateInvoiceError(
                code=NOT_OWNER,
                message="SKU does not belong to the authenticated seller",
                status_code=403,
            )

        if product.deleted:
            raise CreateInvoiceError(
                code=VALIDATION_ERROR,
                message="Product is deleted",
                status_code=400,
            )

        if product.status != Product.Status.MODERATED:
            raise CreateInvoiceError(
                code=VALIDATION_ERROR,
                message="Invoice items require product status MODERATED",
                status_code=400,
            )

    with transaction.atomic():
        invoice = Invoice.objects.create(
            seller_id=seller_id,
            status=Invoice.Status.CREATED,
        )
        InvoiceItem.objects.bulk_create(
            [
                InvoiceItem(
                    invoice=invoice,
                    sku_id=row["sku_id"],
                    quantity=row["quantity"],
                    accepted_quantity=0,
                )
                for row in items
            ]
        )

    return Invoice.objects.prefetch_related("items__sku").get(pk=invoice.pk)
