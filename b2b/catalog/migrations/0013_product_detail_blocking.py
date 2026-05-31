import uuid

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0012_moderation_outbox'),
    ]

    operations = [
        migrations.CreateModel(
            name='BlockingReason',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('title', models.CharField(max_length=200)),
                ('comment', models.TextField(blank=True, default='')),
            ],
            options={
                'ordering': ['title'],
            },
        ),
        migrations.AddField(
            model_name='product',
            name='field_reports',
            field=models.JSONField(blank=True, default=list),
        ),
    ]
