from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0002_order_cancel_reason"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="status_history",
            field=models.JSONField(blank=True, default=list),
        ),
    ]
