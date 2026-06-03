from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0016_processed_moderation_openapi"),
    ]

    operations = [
        migrations.AlterField(
            model_name="b2coutboxevent",
            name="sku_id",
            field=models.UUIDField(blank=True, db_index=True, null=True),
        ),
    ]
