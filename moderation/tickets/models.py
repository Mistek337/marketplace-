import uuid

from django.db import models


class Moderator(models.Model):
    class Role(models.TextChoices):
        MODERATOR = 'MODERATOR', 'Moderator'
        ADMIN = 'ADMIN', 'Admin'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    password = models.CharField(max_length=128)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100, blank=True, default='')
    role = models.CharField(
        max_length=16,
        choices=Role.choices,
        default=Role.MODERATOR,
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_login_at = models.DateTimeField(null=True, blank=True)

    @property
    def is_authenticated(self) -> bool:
        return True

    @property
    def is_anonymous(self) -> bool:
        return False

    def __str__(self) -> str:
        return self.email


class RevokedRefreshToken(models.Model):
    jti = models.UUIDField(primary_key=True)
    revoked_at = models.DateTimeField(auto_now_add=True)


class Ticket(models.Model):
    class Kind(models.TextChoices):
        CREATE = 'CREATE', 'Create'
        EDIT = 'EDIT', 'Edit'

    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        IN_REVIEW = 'IN_REVIEW', 'In review'
        APPROVED = 'APPROVED', 'Approved'
        BLOCKED = 'BLOCKED', 'Blocked'
        HARD_BLOCKED = 'HARD_BLOCKED', 'Hard blocked'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product_id = models.UUIDField(db_index=True)
    seller_id = models.UUIDField(db_index=True)
    category_id = models.UUIDField(null=True, blank=True, db_index=True)
    kind = models.CharField(max_length=16, choices=Kind.choices)
    status = models.CharField(
        max_length=32,
        choices=Status.choices,
        default=Status.PENDING,
    )
    queue_priority = models.PositiveSmallIntegerField(default=3)
    assigned_moderator = models.ForeignKey(
        Moderator,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='tickets',
    )
    json_before = models.JSONField(null=True, blank=True)
    json_after = models.JSONField(default=dict)
    field_reports = models.JSONField(default=list, blank=True)
    product_revision = models.PositiveIntegerField(default=0)
    claimed_revision = models.PositiveIntegerField(null=True, blank=True)
    decision_comment = models.TextField(blank=True, default='')
    claimed_at = models.DateTimeField(null=True, blank=True)
    decision_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def is_terminal(self) -> bool:
        return self.status == self.Status.HARD_BLOCKED

    class Meta:
        ordering = ['created_at']


class BlockingReason(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=64, unique=True)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, default='')
    hard_block = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['code']

    def __str__(self) -> str:
        return self.code


class B2BOutboxEvent(models.Model):
    """Исходящие события в B2B (идемпотентность по idempotency_key)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    idempotency_key = models.UUIDField(unique=True, db_index=True)
    ticket = models.ForeignKey(
        Ticket,
        on_delete=models.CASCADE,
        related_name='b2b_outbox_events',
    )
    event = models.CharField(max_length=32, default='MODERATED')
    product_id = models.UUIDField(db_index=True)
    seller_id = models.UUIDField()
    payload = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['created_at']
