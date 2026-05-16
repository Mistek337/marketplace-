from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0010_openapi_sku_images'),
    ]

    operations = [
        migrations.AddField(
            model_name='category',
            name='is_active',
            field=models.BooleanField(default=True),
        ),
    ]
