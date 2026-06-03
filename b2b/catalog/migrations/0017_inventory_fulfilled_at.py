from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0016_processed_moderation_openapi"),
    ]

    operations = [
        migrations.AddField(
            model_name="inventoryreservation",
            name="fulfilled_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
