import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0016_processed_moderation_openapi"),
        ("invoices", "0001_initial"),
    ]

    operations = [
        migrations.DeleteModel(
            name="InvoiceLine",
        ),
        migrations.DeleteModel(
            name="Invoice",
        ),
        migrations.CreateModel(
            name="Invoice",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("seller_id", models.UUIDField(db_index=True)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("CREATED", "Created"),
                            ("PARTIALLY_ACCEPTED", "Partially accepted"),
                            ("ACCEPTED", "Accepted"),
                            ("CANCELLED", "Cancelled"),
                        ],
                        default="CREATED",
                        max_length=32,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("accepted_at", models.DateTimeField(blank=True, null=True)),
                ("accepted_by", models.UUIDField(blank=True, null=True)),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="InvoiceItem",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("quantity", models.PositiveIntegerField()),
                ("accepted_quantity", models.PositiveIntegerField(default=0)),
                (
                    "invoice",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="items",
                        to="invoices.invoice",
                    ),
                ),
                (
                    "sku",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="invoice_items",
                        to="catalog.sku",
                    ),
                ),
            ],
            options={
                "ordering": ["id"],
            },
        ),
        migrations.AddConstraint(
            model_name="invoiceitem",
            constraint=models.UniqueConstraint(
                fields=("invoice", "sku"),
                name="uniq_invoice_sku_item",
            ),
        ),
    ]
