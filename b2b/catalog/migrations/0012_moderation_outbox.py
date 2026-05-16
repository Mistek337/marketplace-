from django.db import migrations, models
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0011_category_is_active'),
    ]

    operations = [
        migrations.CreateModel(
            name='ModerationOutboxEvent',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('idempotency_key', models.UUIDField(db_index=True, unique=True)),
                ('event', models.CharField(max_length=32)),
                ('product_id', models.UUIDField(db_index=True)),
                ('seller_id', models.UUIDField(blank=True, null=True)),
                ('payload', models.JSONField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('sent_at', models.DateTimeField(blank=True, null=True)),
            ],
            options={
                'ordering': ['created_at'],
            },
        ),
    ]
