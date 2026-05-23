import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Address",
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
                ("country", models.CharField(max_length=100)),
                ("region", models.CharField(blank=True, default="", max_length=200)),
                ("city", models.CharField(max_length=200)),
                ("street", models.CharField(max_length=200)),
                ("building", models.CharField(max_length=50)),
                ("apartment", models.CharField(blank=True, default="", max_length=50)),
                ("postal_code", models.CharField(blank=True, default="", max_length=20)),
                ("recipient_name", models.CharField(blank=True, default="", max_length=200)),
                ("recipient_phone", models.CharField(blank=True, default="", max_length=20)),
                ("is_default", models.BooleanField(default=False)),
                ("comment", models.CharField(blank=True, default="", max_length=500)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="addresses",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="PaymentMethod",
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
                (
                    "type",
                    models.CharField(
                        choices=[
                            ("CARD", "Card"),
                            ("SBP", "SBP"),
                            ("WALLET", "Wallet"),
                        ],
                        max_length=16,
                    ),
                ),
                ("card_last4", models.CharField(blank=True, default="", max_length=4)),
                ("card_brand", models.CharField(blank=True, default="", max_length=32)),
                ("is_default", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="payment_methods",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="Order",
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
                ("number", models.CharField(max_length=32, unique=True)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("CREATED", "Created"),
                            ("PAID", "Paid"),
                            ("ASSEMBLING", "Assembling"),
                            ("DELIVERING", "Delivering"),
                            ("DELIVERED", "Delivered"),
                            ("CANCELLED", "Cancelled"),
                            ("CANCEL_PENDING", "Cancel pending"),
                        ],
                        default="CREATED",
                        max_length=32,
                    ),
                ),
                ("idempotency_key", models.UUIDField(db_index=True, unique=True)),
                ("request_hash", models.CharField(max_length=64)),
                ("address_snapshot", models.JSONField()),
                ("payment_method_snapshot", models.JSONField()),
                ("subtotal", models.PositiveBigIntegerField()),
                ("delivery_cost", models.PositiveBigIntegerField(default=0)),
                ("total", models.PositiveBigIntegerField()),
                ("comment", models.TextField(blank=True, default="")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("paid_at", models.DateTimeField(blank=True, null=True)),
                (
                    "buyer",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="orders",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="OrderItem",
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
                ("sku_id", models.UUIDField(db_index=True)),
                ("product_id", models.UUIDField(db_index=True)),
                ("product_title", models.CharField(max_length=512)),
                ("sku_name", models.CharField(max_length=512)),
                ("sku_code", models.CharField(blank=True, default="", max_length=255)),
                ("quantity", models.PositiveIntegerField()),
                ("unit_price", models.PositiveBigIntegerField()),
                ("line_total", models.PositiveBigIntegerField()),
                ("image_url", models.CharField(blank=True, default="", max_length=2048)),
                (
                    "order",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="items",
                        to="orders.order",
                    ),
                ),
            ],
            options={"ordering": ["id"]},
        ),
    ]
