import uuid

import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0008_sku_article"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="slug",
            field=models.SlugField(blank=True, default="", max_length=255),
        ),
        migrations.AddField(
            model_name="product",
            name="blocking_reason_id",
            field=models.UUIDField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="product",
            name="moderator_comment",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.DeleteModel(
            name="ProductCharacteristic",
        ),
        migrations.DeleteModel(
            name="ProductImage",
        ),
        migrations.CreateModel(
            name="ProductImage",
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
                ("url", models.CharField(max_length=2048)),
                ("ordering", models.PositiveIntegerField(default=0)),
                (
                    "product",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="image_rows",
                        to="catalog.product",
                    ),
                ),
            ],
            options={
                "ordering": ["ordering", "id"],
            },
        ),
        migrations.CreateModel(
            name="ProductCharacteristic",
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
                ("name", models.CharField(max_length=255)),
                ("value", models.CharField(max_length=1024)),
                (
                    "product",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="characteristic_rows",
                        to="catalog.product",
                    ),
                ),
            ],
            options={
                "ordering": ["id"],
            },
        ),
        migrations.AddField(
            model_name="sku",
            name="created_at",
            field=models.DateTimeField(
                auto_now_add=True,
                default=django.utils.timezone.now,
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="sku",
            name="updated_at",
            field=models.DateTimeField(auto_now=True),
        ),
    ]
