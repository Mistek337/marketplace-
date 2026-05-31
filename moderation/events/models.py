import uuid

from django.db import models


class ProcessedB2BEvent(models.Model):
    """Идемпотентность входящих событий от B2B (TTL на уровне бизнес-логики / cron)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    idempotency_key = models.UUIDField(unique=True, db_index=True)
    event_type = models.CharField(max_length=32)
    product_id = models.UUIDField(db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']
