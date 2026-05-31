from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0015_processed_moderation_event"),
    ]

    operations = [
        migrations.AddField(
            model_name="processedmoderationevent",
            name="sender_service",
            field=models.CharField(db_index=True, default="moderation", max_length=64),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="processedmoderationevent",
            name="occurred_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="processedmoderationevent",
            name="idempotency_key",
            field=models.UUIDField(db_index=True),
        ),
        migrations.AlterUniqueTogether(
            name="processedmoderationevent",
            unique_together={("sender_service", "idempotency_key")},
        ),
    ]
