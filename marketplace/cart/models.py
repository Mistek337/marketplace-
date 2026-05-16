import uuid

from django.conf import settings
from django.db import models


class Cart(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="cart",
    )
    session_id = models.UUIDField(null=True, blank=True, unique=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self) -> str:
        if self.user_id:
            return f"Cart(user={self.user_id})"
        return f"Cart(session={self.session_id})"


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name="items")
    sku_id = models.UUIDField(db_index=True)
    product_id = models.UUIDField(db_index=True)
    quantity = models.PositiveIntegerField(default=1)
    unit_price_at_add = models.PositiveBigIntegerField(
        null=True,
        blank=True,
        help_text="Price in kopecks at add time",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at", "id"]
        constraints = [
            models.UniqueConstraint(fields=["cart", "sku_id"], name="cart_item_unique_sku"),
        ]
