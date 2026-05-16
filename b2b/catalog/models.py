import uuid

from django.core.exceptions import ValidationError
from django.db import models


class Category(models.Model):
    """Дерево категорий: корень с parent=NULL, дочерние ссылаются на родителя."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    parent = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='children',
    )

    class Meta:
        verbose_name_plural = 'categories'
        ordering = ['id']

    def __str__(self) -> str:
        return self.name

    def clean(self) -> None:
        super().clean()
        if self.parent_id and self.parent_id == self.pk:
            raise ValidationError({'parent': 'Категория не может быть родителем самой себя.'})


class Product(models.Model):
    class Status(models.TextChoices):
        CREATED = 'CREATED', 'Created'
        ON_MODERATION = 'ON_MODERATION', 'On moderation'
        MODERATED = 'MODERATED', 'Moderated'
        HARD_BLOCKED = 'HARD_BLOCKED', 'Hard blocked'
        BLOCKED = 'BLOCKED', 'Blocked'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    seller_id = models.UUIDField(null=True, blank=True, db_index=True)
    title = models.CharField(max_length=512)
    description = models.TextField(blank=True)
    status = models.CharField(
        max_length=32,
        choices=Status.choices,
        default=Status.CREATED,
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name='products',
    )
    deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['id']

    def __str__(self) -> str:
        return self.title


class ProductCharacteristic(models.Model):
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='characteristic_rows',
    )
    name = models.CharField(max_length=255)
    value = models.CharField(max_length=1024)

    class Meta:
        ordering = ['id']


class ProductImage(models.Model):
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='image_rows',
    )
    url = models.CharField(max_length=2048)
    ordering = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['ordering', 'id']


class SKU(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='skus',
    )
    name = models.CharField(max_length=512)
    price = models.PositiveBigIntegerField(
        help_text='Price in minor units (e.g. kopecks), as in API.',
    )
    cost_price = models.PositiveBigIntegerField(default=1)
    discount = models.PositiveBigIntegerField(default=0)
    image = models.CharField(max_length=2048, default="")
    active_quantity = models.PositiveIntegerField(default=0)
    reserved_quantity = models.PositiveIntegerField(default=0)
    article = models.CharField(max_length=255, blank=True, default="")

    class Meta:
        ordering = ['id']

    def __str__(self) -> str:
        return f'{self.product_id}:{self.name}'


class SKUCharacteristic(models.Model):
    sku = models.ForeignKey(
        SKU,
        on_delete=models.CASCADE,
        related_name='characteristic_rows',
    )
    name = models.CharField(max_length=255)
    value = models.CharField(max_length=1024)

    class Meta:
        ordering = ['id']
