from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0006_product_deleted_sku_discount_image"),
    ]

    operations = [
        migrations.AlterField(
            model_name="product",
            name="status",
            field=models.CharField(
                choices=[
                    ("CREATED", "Created"),
                    ("ON_MODERATION", "On moderation"),
                    ("MODERATED", "Moderated"),
                    ("HARD_BLOCKED", "Hard blocked"),
                    ("BLOCKED", "Blocked"),
                ],
                default="CREATED",
                max_length=32,
            ),
        ),
        migrations.AddField(
            model_name="sku",
            name="cost_price",
            field=models.PositiveBigIntegerField(default=1),
        ),
        migrations.AddField(
            model_name="sku",
            name="reserved_quantity",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AlterField(
            model_name="sku",
            name="image",
            field=models.CharField(default="", max_length=2048),
        ),
    ]
