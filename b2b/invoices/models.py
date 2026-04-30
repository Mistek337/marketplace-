from django.db import models


class Invoice(models.Model):
    """
    Приходная накладная: до приёмки остатки SKU не меняются.
    """

    class Status(models.TextChoices):
        CREATED = 'CREATED', 'Created'
        ACCEPTED = 'ACCEPTED', 'Accepted'
        CANCELLED = 'CANCELLED', 'Cancelled'

    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.CREATED,
    )
    note = models.CharField(max_length=1024, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-id']

    def __str__(self) -> str:
        return f'Invoice #{self.pk} ({self.status})'


class InvoiceLine(models.Model):
    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.CASCADE,
        related_name='lines',
    )
    sku = models.ForeignKey(
        'catalog.SKU',
        on_delete=models.PROTECT,
        related_name='invoice_lines',
    )
    quantity = models.PositiveIntegerField()

    class Meta:
        ordering = ['id']
        constraints = [
            models.UniqueConstraint(
                fields=('invoice', 'sku'),
                name='uniq_invoice_sku_line',
            ),
        ]
