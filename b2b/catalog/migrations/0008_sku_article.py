from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0007_sku_cost_reserved_and_hard_blocked"),
    ]

    operations = [
        migrations.AddField(
            model_name="sku",
            name="article",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
    ]
