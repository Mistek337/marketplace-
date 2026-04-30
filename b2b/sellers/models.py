import uuid

from django.db import models


class Seller(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    password = models.CharField(max_length=128)
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    middle_name = models.CharField(max_length=150, null=True, blank=True)
    company_name = models.CharField(max_length=255)
    phone = models.CharField(max_length=32, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    @property
    def is_authenticated(self):
        return True

    @property
    def is_anonymous(self):
        return False


class RevokedRefreshToken(models.Model):
    jti = models.UUIDField(unique=True)
    seller = models.ForeignKey(
        Seller, on_delete=models.CASCADE, related_name="revoked_refresh_tokens"
    )
    revoked_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-revoked_at"]

