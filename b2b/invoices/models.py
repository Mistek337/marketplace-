import uuid

from django.db import models


class Invoice(models.Model):
    """Приходная накладная (OpenAPI InvoiceResponse)."""

    class Status(models.TextChoices):
        CREATED = "CREATED", "Created"
        PARTIALLY_ACCEPTED = "PARTIALLY_ACCEPTED", "Partially accepted"
        ACCEPTED = "ACCEPTED", "Accepted"
        CANCELLED = "CANCELLED", "Cancelled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    seller_id = models.UUIDField(db_index=True)
    status = models.CharField(
        max_length=32,
        choices=Status.choices,
        default=Status.CREATED,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    accepted_by = models.UUIDField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Invoice {self.id} ({self.status})"


class InvoiceItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.CASCADE,
        related_name="items",
    )
    sku = models.ForeignKey(
        "catalog.SKU",
        on_delete=models.PROTECT,
        related_name="invoice_items",
    )
    quantity = models.PositiveIntegerField()
    accepted_quantity = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(
                fields=("invoice", "sku"),
                name="uniq_invoice_sku_item",
            ),
        ]
