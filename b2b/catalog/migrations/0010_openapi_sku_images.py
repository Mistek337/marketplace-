import uuid

import django.db.models.deletion
from django.db import migrations, models


def copy_sku_image_to_rows(apps, schema_editor):
    SKU = apps.get_model("catalog", "SKU")
    SKUImage = apps.get_model("catalog", "SKUImage")
    for sku in SKU.objects.all():
        url = (getattr(sku, "image", None) or "").strip()
        if url:
            SKUImage.objects.create(sku_id=sku.pk, url=url, ordering=0)


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0009_openapi_product_card"),
    ]

    operations = [
        migrations.AlterField(
            model_name="sku",
            name="cost_price",
            field=models.PositiveBigIntegerField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="sku",
            name="article",
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.DeleteModel(
            name="SKUCharacteristic",
        ),
        migrations.CreateModel(
            name="SKUCharacteristic",
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
                    "sku",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="characteristic_rows",
                        to="catalog.sku",
                    ),
                ),
            ],
            options={
                "ordering": ["id"],
            },
        ),
        migrations.CreateModel(
            name="SKUImage",
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
                    "sku",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="image_rows",
                        to="catalog.sku",
                    ),
                ),
            ],
            options={
                "ordering": ["ordering", "id"],
            },
        ),
        migrations.RunPython(copy_sku_image_to_rows, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name="sku",
            name="image",
        ),
    ]
