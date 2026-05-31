import uuid

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0014_merge_catalog_0013"),
    ]

    operations = [
        migrations.CreateModel(
            name="ProcessedModerationEvent",
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
                ("event_type", models.CharField(max_length=16)),
                ("product_id", models.UUIDField(db_index=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "ordering": ["created_at"],
            },
        ),
        migrations.AlterField(
            model_name="b2coutboxevent",
            name="sku_id",
            field=models.UUIDField(blank=True, db_index=True, null=True),
        ),
    ]
