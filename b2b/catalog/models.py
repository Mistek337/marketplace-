import uuid

from django.core.exceptions import ValidationError
from django.db import models
from django.utils.text import slugify


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
    slug = models.SlugField(max_length=255, blank=True, default="")
    description = models.TextField(blank=True)
    blocking_reason_id = models.UUIDField(null=True, blank=True)
    moderator_comment = models.TextField(blank=True, default="")
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

    def ensure_slug(self) -> None:
        if self.slug:
            return
        base = slugify(self.title) or "product"
        self.slug = base[:240]
        if Product.objects.filter(slug=self.slug).exclude(pk=self.pk).exists():
            self.slug = f"{self.slug[:220]}-{str(self.pk)[:8]}"


class ProductCharacteristic(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
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
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
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
    cost_price = models.PositiveBigIntegerField(null=True, blank=True)
    discount = models.PositiveBigIntegerField(default=0)
    active_quantity = models.PositiveIntegerField(default=0)
    reserved_quantity = models.PositiveIntegerField(default=0)
    article = models.CharField(max_length=255, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['id']

    @property
    def stock_quantity(self) -> int:
        return self.active_quantity + self.reserved_quantity

    def __str__(self) -> str:
        return f'{self.product_id}:{self.name}'


class SKUImage(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sku = models.ForeignKey(
        SKU,
        on_delete=models.CASCADE,
        related_name='image_rows',
    )
    url = models.CharField(max_length=2048)
    ordering = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['ordering', 'id']


class SKUCharacteristic(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sku = models.ForeignKey(
        SKU,
        on_delete=models.CASCADE,
        related_name='characteristic_rows',
    )
    name = models.CharField(max_length=255)
    value = models.CharField(max_length=1024)

    class Meta:
        ordering = ['id']
