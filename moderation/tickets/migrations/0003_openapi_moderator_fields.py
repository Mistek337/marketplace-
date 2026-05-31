import uuid

from django.contrib.auth.hashers import make_password
from django.db import migrations, models


def set_default_passwords(apps, schema_editor):
    Moderator = apps.get_model('tickets', 'Moderator')
    for moderator in Moderator.objects.all():
        if not moderator.password:
            moderator.password = make_password('change-me-in-production')
            moderator.save(update_fields=['password'])


class Migration(migrations.Migration):

    dependencies = [
        ('tickets', '0002_blocking_reason'),
    ]

    operations = [
        migrations.CreateModel(
            name='RevokedRefreshToken',
            fields=[
                ('jti', models.UUIDField(primary_key=True, serialize=False)),
                ('revoked_at', models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.AddField(
            model_name='moderator',
            name='first_name',
            field=models.CharField(default='Moderator', max_length=100),
        ),
        migrations.AddField(
            model_name='moderator',
            name='last_name',
            field=models.CharField(blank=True, default='', max_length=100),
        ),
        migrations.AddField(
            model_name='moderator',
            name='password',
            field=models.CharField(default='', max_length=128),
        ),
        migrations.AddField(
            model_name='moderator',
            name='role',
            field=models.CharField(
                choices=[('MODERATOR', 'Moderator'), ('ADMIN', 'Admin')],
                default='MODERATOR',
                max_length=16,
            ),
        ),
        migrations.AddField(
            model_name='moderator',
            name='last_login_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='ticket',
            name='category_id',
            field=models.UUIDField(blank=True, db_index=True, null=True),
        ),
        migrations.AddField(
            model_name='ticket',
            name='field_reports',
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.RunPython(set_default_passwords, migrations.RunPython.noop),
    ]
