import uuid

from django.conf import settings
from django.db import models


class Favorite(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="favorites",
    )
    product_id = models.UUIDField(db_index=True)

    class Meta:
        unique_together = ("user", "product_id")
        ordering = ["-id"]
