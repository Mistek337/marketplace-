"""
Временные эндпоинты для локальной отладки каталога.
Удалить или отключить перед продакшеном.
"""

from django.conf import settings
from django.db import DatabaseError, transaction
from django.db.models import Prefetch
from django.utils.text import slugify
from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Product, ProductImage, SKU, SKUImage
from .serializers import ProductDetailSerializer


class _ImageInSerializer(serializers.Serializer):
    url = serializers.URLField()
    order = serializers.IntegerField(default=1, min_value=1)


class _SKUInSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
    price = serializers.DecimalField(max_digits=12, decimal_places=2)
    quantity = serializers.IntegerField(min_value=0, default=0)
    characteristics = serializers.ListField(
        child=serializers.DictField(), required=False, default=list
    )
    images = _ImageInSerializer(many=True, required=False, default=list)


class DevSeedProductSerializer(serializers.Serializer):
    """Тело для POST /api/v1/dev/products — создаёт Product + SKU + картинки."""

    title = serializers.CharField(max_length=255)
    slug = serializers.SlugField(
        max_length=255, required=False, allow_blank=True, allow_null=True
    )
    description = serializers.CharField(required=False, default="", allow_blank=True)
    moderation_status = serializers.ChoiceField(
        choices=[c[0] for c in Product.ModerationStatus.choices],
        default=Product.ModerationStatus.PUBLISHED,
    )
    category_id = serializers.UUIDField(required=False, allow_null=True)
    rating = serializers.FloatField(required=False, default=0.0)
    popularity = serializers.IntegerField(required=False, default=0, min_value=0)
    discount = serializers.DecimalField(
        max_digits=5, decimal_places=2, required=False, default=0
    )
    characteristics = serializers.ListField(
        child=serializers.DictField(), required=False, default=list
    )
    images = _ImageInSerializer(many=True, required=False, default=list)
    skus = _SKUInSerializer(many=True, min_length=1)


class DevSeedProductView(APIView):
    """
    POST /api/v1/dev/products — создать товар со SKU (для Postman/тестов).
    Доступно только при DEBUG=True.
    """

    authentication_classes = []
    permission_classes = []

    def post(self, request):
        if not settings.DEBUG:
            return Response(status=status.HTTP_404_NOT_FOUND)

        ser = DevSeedProductSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data

        slug = data.get("slug") or None
        if not slug:
            base = slugify(data["title"]) or "product"
            slug = base
            suffix = 1
            while Product.objects.filter(slug=slug).exists():
                slug = f"{base}-{suffix}"
                suffix += 1

        try:
            with transaction.atomic():
                product = Product.objects.create(
                    slug=slug,
                    title=data["title"],
                    description=data.get("description", ""),
                    category_id=data.get("category_id"),
                    rating=data.get("rating", 0.0),
                    popularity=data.get("popularity", 0),
                    discount=data.get("discount", 0),
                    characteristics=data.get("characteristics") or [],
                    moderation_status=data["moderation_status"],
                )
                for img in data.get("images") or []:
                    ProductImage.objects.create(
                        product=product,
                        url=img["url"],
                        order=img.get("order", 1),
                    )
                for sku_data in data["skus"]:
                    sku = SKU.objects.create(
                        product=product,
                        name=sku_data["name"],
                        price=sku_data["price"],
                        quantity=sku_data.get("quantity", 0),
                        characteristics=sku_data.get("characteristics") or [],
                    )
                    for img in sku_data.get("images") or []:
                        SKUImage.objects.create(
                            sku=sku,
                            url=img["url"],
                            order=img.get("order", 1),
                        )

                product = (
                    Product.objects.prefetch_related(
                        "images",
                        Prefetch(
                            "skus",
                            queryset=SKU.objects.prefetch_related("images"),
                        ),
                    )
                    .get(pk=product.pk)
                )
        except DatabaseError as exc:
            return Response(
                {
                    "message": "Database error (often missing migrations). "
                    "Run: python manage.py migrate",
                    "detail": str(exc),
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        return Response(
            ProductDetailSerializer(product).data,
            status=status.HTTP_201_CREATED,
        )
