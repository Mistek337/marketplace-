"""Синхронизация с БД: колонка added_at могла появиться вручную; Django должна её заполнять."""

import django.utils.timezone
from django.db import migrations, models


def _drop_added_at_if_exists(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(
        "ALTER TABLE favorites_favorite DROP COLUMN IF EXISTS added_at;"
    )


def _noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("favorites", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(_drop_added_at_if_exists, _noop_reverse),
        migrations.AddField(
            model_name="favorite",
            name="added_at",
            field=models.DateTimeField(default=django.utils.timezone.now),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name="favorite",
            name="added_at",
            field=models.DateTimeField(auto_now_add=True),
        ),
    ]
