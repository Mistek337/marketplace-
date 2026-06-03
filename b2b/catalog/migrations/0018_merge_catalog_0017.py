from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0017_b2c_outbox_sku_nullable"),
        ("catalog", "0017_inventory_fulfilled_at"),
    ]

    operations = []
