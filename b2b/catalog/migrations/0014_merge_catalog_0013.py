from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0013_inventory_reservation_outbox"),
        ("catalog", "0013_product_detail_blocking"),
    ]

    operations = []
