from rest_framework import serializers

from .models import Product, ProductImage, SKU, SKUImage


class SKUImageShortSerializer(serializers.Serializer):
    url = serializers.URLField()
    order = serializers.IntegerField()


class SKUShortSerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()

    class Meta:
        model = SKU
        fields = ("name", "price", "image")

    def get_image(self, obj):
        first = obj.images.order_by("order").first()
        if not first:
            return None
        return {"url": first.url, "order": first.order}


class SKUImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = SKUImage
        fields = ("url", "order")


class SKUDetailSerializer(serializers.ModelSerializer):
    images = SKUImageSerializer(many=True)

    class Meta:
        model = SKU
        fields = ("id", "name", "price", "quantity", "characteristics", "images")


class ProductListItemSerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()
    price = serializers.SerializerMethodField()
    in_stock = serializers.SerializerMethodField()
    is_in_cart = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = ("id", "title", "image", "price", "in_stock", "is_in_cart")

    def get_image(self, obj):
        # Берём первую картинку первой SKU, если есть
        for sku in obj.skus.all():
            first = sku.images.order_by("order").first()
            if first:
                return first.url
        return None

    def get_price(self, obj):
        prices = [sku.price for sku in obj.skus.all()]
        return min(prices) if prices else None

    def get_in_stock(self, obj):
        return any(sku.quantity > 0 for sku in obj.skus.all())

    def get_is_in_cart(self, obj):
        # Корзины пока нет — позже свяжем с cart-сервисом/моделью
        return False


class ProductImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImage
        fields = ("url", "order")


class ProductDetailSerializer(serializers.ModelSerializer):
    images = ProductImageSerializer(many=True)
    status = serializers.SerializerMethodField()
    skus = SKUDetailSerializer(many=True)

    class Meta:
        model = Product
        fields = (
            "id",
            "slug",
            "title",
            "description",
            "images",
            "status",
            "characteristics",
            "skus",
        )

    def get_status(self, obj):
        # В схеме на скрине статус товара выглядит как MODERATED
        if obj.moderation_status == Product.ModerationStatus.PUBLISHED:
            return "MODERATED"
        return obj.moderation_status

