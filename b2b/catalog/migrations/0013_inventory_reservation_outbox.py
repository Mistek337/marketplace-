import uuid

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0012_moderation_outbox"),
    ]

    operations = [
        migrations.CreateModel(
            name="InventoryReservation",
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
                ("idempotency_key", models.UUIDField(db_index=True, unique=True)),
                ("order_id", models.UUIDField(db_index=True, unique=True)),
                ("items", models.JSONField()),
                ("response_payload", models.JSONField()),
                ("reserved_at", models.DateTimeField()),
                ("unreserved_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "ordering": ["created_at"],
            },
        ),
        migrations.CreateModel(
            name="B2COutboxEvent",
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
                ("idempotency_key", models.UUIDField(db_index=True, unique=True)),
                ("event", models.CharField(max_length=32)),
                ("sku_id", models.UUIDField(db_index=True)),
                ("product_id", models.UUIDField(db_index=True)),
                ("payload", models.JSONField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("sent_at", models.DateTimeField(blank=True, null=True)),
            ],
            options={
                "ordering": ["created_at"],
            },
        ),
    ]
