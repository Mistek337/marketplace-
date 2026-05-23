import hashlib
import json
import uuid

from django.conf import settings
from django.db import models


class Address(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="addresses",
    )
    country = models.CharField(max_length=100)
    region = models.CharField(max_length=200, blank=True, default="")
    city = models.CharField(max_length=200)
    street = models.CharField(max_length=200)
    building = models.CharField(max_length=50)
    apartment = models.CharField(max_length=50, blank=True, default="")
    postal_code = models.CharField(max_length=20, blank=True, default="")
    recipient_name = models.CharField(max_length=200, blank=True, default="")
    recipient_phone = models.CharField(max_length=20, blank=True, default="")
    is_default = models.BooleanField(default=False)
    comment = models.CharField(max_length=500, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class PaymentMethod(models.Model):
    class Type(models.TextChoices):
        CARD = "CARD", "Card"
        SBP = "SBP", "SBP"
        WALLET = "WALLET", "Wallet"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="payment_methods",
    )
    type = models.CharField(max_length=16, choices=Type.choices)
    card_last4 = models.CharField(max_length=4, blank=True, default="")
    card_brand = models.CharField(max_length=32, blank=True, default="")
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class Order(models.Model):
    class Status(models.TextChoices):
        CREATED = "CREATED", "Created"
        PAID = "PAID", "Paid"
        ASSEMBLING = "ASSEMBLING", "Assembling"
        DELIVERING = "DELIVERING", "Delivering"
        DELIVERED = "DELIVERED", "Delivered"
        CANCELLED = "CANCELLED", "Cancelled"
        CANCEL_PENDING = "CANCEL_PENDING", "Cancel pending"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    buyer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="orders",
    )
    number = models.CharField(max_length=32, unique=True)
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.CREATED)
    idempotency_key = models.UUIDField(unique=True, db_index=True)
    request_hash = models.CharField(max_length=64)
    address_snapshot = models.JSONField()
    payment_method_snapshot = models.JSONField()
    subtotal = models.PositiveBigIntegerField()
    delivery_cost = models.PositiveBigIntegerField(default=0)
    total = models.PositiveBigIntegerField()
    comment = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]


class OrderItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    sku_id = models.UUIDField(db_index=True)
    product_id = models.UUIDField(db_index=True)
    product_title = models.CharField(max_length=512)
    sku_name = models.CharField(max_length=512)
    sku_code = models.CharField(max_length=255, blank=True, default="")
    quantity = models.PositiveIntegerField()
    unit_price = models.PositiveBigIntegerField()
    line_total = models.PositiveBigIntegerField()
    image_url = models.CharField(max_length=2048, blank=True, default="")

    class Meta:
        ordering = ["id"]


def _json_default(value):
    if isinstance(value, uuid.UUID):
        return str(value)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def hash_checkout_request(body: dict) -> str:
    payload = json.dumps(
        body,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=_json_default,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
