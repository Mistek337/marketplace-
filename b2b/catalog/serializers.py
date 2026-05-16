from rest_framework import serializers

from .models import (
    Category,
    Product,
    ProductCharacteristic,
    ProductImage,
    SKU,
    SKUCharacteristic,
)


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ('id', 'name', 'parent_id', 'created_at')


class CategoryFlatSerializer(serializers.ModelSerializer):
    parent_id = serializers.UUIDField(allow_null=True, read_only=True)

    class Meta:
        model = Category
        fields = ('id', 'name', 'parent_id', 'created_at')


class CategoryCreateSerializer(serializers.ModelSerializer):
    parent_id = serializers.UUIDField(required=False, allow_null=True)

    class Meta:
        model = Category
        fields = ('name', 'parent_id')

    def validate_parent_id(self, value):
        if value is None:
            return value
        if not Category.objects.filter(id=value).exists():
            raise serializers.ValidationError("Invalid parent_id")
        return value

    def create(self, validated_data):
        parent_id = validated_data.pop('parent_id', None)
        if parent_id:
            validated_data['parent_id'] = parent_id
        return Category.objects.create(**validated_data)


class CategoryWithChildrenResponseSerializer(serializers.ModelSerializer):
    children = CategoryFlatSerializer(many=True, read_only=True)

    class Meta:
        model = Category
        fields = ('id', 'name', 'parent_id', 'created_at', 'children')


class CategoryUpdateSerializer(serializers.ModelSerializer):
    parent_id = serializers.UUIDField(required=False, allow_null=True)

    class Meta:
        model = Category
        fields = ('name', 'parent_id')
        extra_kwargs = {
            "name": {"required": False},
        }

    def validate_parent_id(self, value):
        if value is None:
            return value
        if not Category.objects.filter(id=value).exists():
            raise serializers.ValidationError("Invalid parent_id")
        return value

    def validate(self, attrs):
        parent_id = attrs.get("parent_id", serializers.empty)
        if parent_id is serializers.empty:
            return attrs
        instance = self.instance
        if instance and parent_id == instance.id:
            raise serializers.ValidationError({"parent_id": "Category cannot be parent of itself"})
        return attrs


class CategoryRefWriteSerializer(serializers.Serializer):
    """Только выбор существующей категории по id (дерево ведёт модерация / B2B)."""

    id = serializers.PrimaryKeyRelatedField(queryset=Category.objects.all())


class ProductImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImage
        fields = ('id', 'url', 'ordering')


class ProductImageCreateSerializer(serializers.Serializer):
    url = serializers.CharField(max_length=2048)
    ordering = serializers.IntegerField(default=0, required=False, min_value=0)


class CharacteristicWriteSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
    value = serializers.CharField(max_length=1024)


class SKUCharacteristicSerializer(serializers.ModelSerializer):
    class Meta:
        model = SKUCharacteristic
        fields = ('name', 'value')


class SKUCharacteristicResponseSerializer(serializers.ModelSerializer):
    class Meta:
        model = SKUCharacteristic
        fields = ('id', 'name', 'value')


class SKUImageResponseSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    url = serializers.CharField()
    ordering = serializers.IntegerField()


class SKUResponseSerializer(serializers.ModelSerializer):
    """Seller-view SKU (OpenAPI SKUResponse)."""

    product_id = serializers.UUIDField(read_only=True)
    stock_quantity = serializers.IntegerField(read_only=True)
    images = serializers.SerializerMethodField()
    characteristics = SKUCharacteristicResponseSerializer(
        source='characteristic_rows',
        many=True,
        read_only=True,
    )

    class Meta:
        model = SKU
        fields = (
            'id',
            'product_id',
            'name',
            'price',
            'discount',
            'cost_price',
            'stock_quantity',
            'active_quantity',
            'reserved_quantity',
            'article',
            'images',
            'characteristics',
            'created_at',
            'updated_at',
        )

    def get_images(self, obj: SKU) -> list[dict]:
        if not obj.image:
            return []
        return [
            {
                'id': str(obj.id),
                'url': obj.image,
                'ordering': 0,
            }
        ]


class SKUSerializer(serializers.ModelSerializer):
    product_id = serializers.UUIDField(source='product.id', read_only=True)
    active_quantity = serializers.IntegerField(read_only=True)
    reserved_quantity = serializers.IntegerField(read_only=True)
    characteristics = SKUCharacteristicSerializer(
        source='characteristic_rows',
        many=True,
        read_only=True,
    )

    class Meta:
        model = SKU
        fields = (
            'id',
            'product_id',
            'name',
            'price',
            'cost_price',
            'discount',
            'image',
            'active_quantity',
            'reserved_quantity',
            'characteristics',
        )


class ProductCharacteristicSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductCharacteristic
        fields = ('id', 'name', 'value')


class ProductDetailSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)
    category_id = serializers.UUIDField(read_only=True)
    images = ProductImageSerializer(source='image_rows', many=True, read_only=True)
    characteristics = ProductCharacteristicSerializer(
        source='characteristic_rows',
        many=True,
        read_only=True,
    )
    skus = SKUSerializer(many=True, read_only=True)
    blocked = serializers.SerializerMethodField()
    blocking_reason = serializers.SerializerMethodField()
    field_reports = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = (
            'id',
            'seller_id',
            'category_id',
            'title',
            'description',
            'status',
            'deleted',
            'blocked',
            'category',
            'images',
            'characteristics',
            'skus',
            'blocking_reason',
            'field_reports',
            'created_at',
            'updated_at',
        )

    def get_blocked(self, obj: Product) -> bool:
        return obj.status in (Product.Status.BLOCKED, Product.Status.HARD_BLOCKED)

    def get_blocking_reason(self, obj: Product):
        # Заглушка до интеграции с Moderation: для BLOCKED возвращаем причину в ожидаемой форме.
        if obj.status != Product.Status.BLOCKED:
            return None
        return {
            "id": "00000000-0000-0000-0000-000000000001",
            "title": "Blocked by moderation",
            "comment": "Stub reason until moderation integration is connected",
        }

    def get_field_reports(self, obj: Product):
        # Заглушка до интеграции с Moderation.
        if obj.status != Product.Status.BLOCKED:
            return []
        return [
            {
                "field_name": "description",
                "sku_id": None,
                "comment": "Stub report until moderation integration is connected",
            }
        ]


class ProductResponseSerializer(serializers.ModelSerializer):
    """OpenAPI ProductResponse — ответ POST/GET seller-view."""

    category_id = serializers.UUIDField(read_only=True)
    blocking_reason_id = serializers.UUIDField(read_only=True, allow_null=True)
    images = ProductImageSerializer(source='image_rows', many=True, read_only=True)
    characteristics = ProductCharacteristicSerializer(
        source='characteristic_rows',
        many=True,
        read_only=True,
    )
    skus = SKUResponseSerializer(many=True, read_only=True)

    class Meta:
        model = Product
        fields = (
            'id',
            'seller_id',
            'category_id',
            'title',
            'slug',
            'description',
            'status',
            'deleted',
            'blocking_reason_id',
            'moderator_comment',
            'images',
            'characteristics',
            'skus',
            'created_at',
            'updated_at',
        )


class ProductRefWriteSerializer(serializers.Serializer):
    """Ссылка на существующий товар при создании SKU."""

    id = serializers.PrimaryKeyRelatedField(queryset=Product.objects.all())


class SKUCreateSerializer(serializers.ModelSerializer):
    """
    POST /api/v1/skus — создать SKU у уже существующего товара.
    """

    product_id = serializers.UUIDField()
    name = serializers.CharField(max_length=255, required=False, allow_blank=True)
    price = serializers.IntegerField(required=False)
    cost_price = serializers.IntegerField(required=False)
    discount = serializers.IntegerField(required=False, default=0)
    image = serializers.CharField(required=False, allow_blank=True)
    characteristics = SKUCharacteristicSerializer(many=True, required=False)

    class Meta:
        model = SKU
        fields = (
            'product_id',
            'name',
            'price',
            'cost_price',
            'discount',
            'image',
            'characteristics',
        )

    def validate(self, attrs: dict) -> dict:
        name = (attrs.get('name') or '').strip()
        if not name:
            raise serializers.ValidationError({'name': 'name is required'})
        attrs['name'] = name

        image = (attrs.get('image') or '').strip()
        if not image:
            raise serializers.ValidationError({'image': 'image is required'})
        attrs['image'] = image

        price = attrs.get('price')
        if price is None or int(price) <= 0:
            raise serializers.ValidationError(
                {'price': 'price must be a positive integer (kopecks)'}
            )

        cost_price = attrs.get('cost_price')
        if cost_price is None or int(cost_price) <= 0:
            raise serializers.ValidationError(
                {'cost_price': 'cost_price must be a positive integer (kopecks)'}
            )

        discount = attrs.get('discount', 0)
        if discount is None or int(discount) < 0:
            raise serializers.ValidationError(
                {'discount': 'discount must be a non-negative integer (kopecks)'}
            )
        attrs['discount'] = int(discount)
        return attrs

    def to_representation(self, instance: SKU) -> dict:
        return SKUSerializer(instance, context=self.context).data


class ProductCreateSerializer(serializers.Serializer):
    """
    POST /api/v1/products — OpenAPI ProductCreate.
    Статус CREATED, seller_id из JWT, без SKU.
    """

    title = serializers.CharField(required=True, allow_blank=False, max_length=255)
    description = serializers.CharField(required=True, allow_blank=False, max_length=5000)
    category_id = serializers.UUIDField(
        error_messages={
            'invalid': 'category_id must be a valid UUID',
            'required': "Поле 'category_id' обязательно",
        },
    )
    slug = serializers.SlugField(required=False, allow_blank=True, max_length=255)
    images = ProductImageCreateSerializer(many=True, required=False, default=list)
    characteristics = CharacteristicWriteSerializer(many=True, required=False, default=list)

    def validate_category_id(self, value):
        if not Category.objects.filter(pk=value).exists():
            raise serializers.ValidationError('Category not found')
        return value

    def create(self, validated_data: dict) -> Product:
        category = Category.objects.get(pk=validated_data.pop('category_id'))
        slug = (validated_data.pop('slug', None) or '').strip()
        images_data = validated_data.pop('images', [])
        characteristics_data = validated_data.pop('characteristics', [])
        request = self.context.get('request')

        product = Product.objects.create(
            title=validated_data['title'],
            description=validated_data['description'],
            slug=slug,
            category=category,
            seller_id=getattr(getattr(request, 'user', None), 'id', None),
            status=Product.Status.CREATED,
        )
        product.ensure_slug()
        product.save(update_fields=['slug'])

        for row in images_data:
            ProductImage.objects.create(product=product, **row)
        for row in characteristics_data:
            ProductCharacteristic.objects.create(product=product, **row)

        return product

    def to_representation(self, instance: Product) -> dict:
        return ProductResponseSerializer(instance, context=self.context).data


class ProductUpdateSerializer(serializers.ModelSerializer):
    """
    PUT/PATCH /api/v1/products/{id} — правки карточки без смены статуса через это тело.
    Поля опциональны (частичное обновление). Если переданы images/characteristics — списки заменяются целиком.
    """

    category = CategoryRefWriteSerializer(required=False)
    images = ProductImageSerializer(many=True, required=False)
    characteristics = ProductCharacteristicSerializer(many=True, required=False)

    class Meta:
        model = Product
        fields = ('title', 'description', 'category', 'images', 'characteristics')
        extra_kwargs = {
            'title': {'required': False},
            'description': {'required': False},
        }

    def update(self, instance: Product, validated_data: dict) -> Product:
        category_data = validated_data.pop('category', None)
        images_data = validated_data.pop('images', None)
        characteristics_data = validated_data.pop('characteristics', None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        if category_data is not None:
            instance.category = category_data['id']

        instance.save()

        if images_data is not None:
            instance.image_rows.all().delete()
            for row in images_data:
                ProductImage.objects.create(product=instance, **row)

        if characteristics_data is not None:
            instance.characteristic_rows.all().delete()
            for row in characteristics_data:
                ProductCharacteristic.objects.create(product=instance, **row)

        return instance

    def to_representation(self, instance: Product) -> dict:
        return ProductDetailSerializer(instance, context=self.context).data


class SKUUpdateSerializer(serializers.ModelSerializer):
    """PUT/PATCH /api/v1/skus/{id} — правки SKU (товар не переносится)."""

    active_quantity = serializers.IntegerField(required=False)
    reserved_quantity = serializers.IntegerField(required=False)
    discount = serializers.IntegerField(required=False, min_value=0)
    image = serializers.CharField(required=False, allow_blank=True)
    characteristics = SKUCharacteristicSerializer(many=True, required=False)

    class Meta:
        model = SKU
        fields = (
            'name',
            'price',
            'cost_price',
            'discount',
            'image',
            'active_quantity',
            'reserved_quantity',
            'characteristics',
        )
        extra_kwargs = {
            'name': {'required': False},
            'price': {'required': False},
            'cost_price': {'required': False},
        }

    def update(self, instance: SKU, validated_data: dict) -> SKU:
        characteristics_data = validated_data.pop('characteristics', None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if characteristics_data is not None:
            instance.characteristic_rows.all().delete()
            for row in characteristics_data:
                SKUCharacteristic.objects.create(sku=instance, **row)

        return instance

    def to_representation(self, instance: SKU) -> dict:
        return SKUSerializer(instance, context=self.context).data


class ProductListSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)

    class Meta:
        model = Product
        fields = ('id', 'title', 'status', 'category')


class ProductMyListItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = ("id", "title", "status", "category_id", "created_at")


class B2CCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ("id", "name")


class B2CSKUCharacteristicSerializer(serializers.ModelSerializer):
    class Meta:
        model = SKUCharacteristic
        fields = ("name", "value")


class B2CSKUSerializer(serializers.ModelSerializer):
    active_quantity = serializers.IntegerField(read_only=True)
    characteristics = B2CSKUCharacteristicSerializer(
        source="characteristic_rows", many=True, read_only=True
    )

    class Meta:
        model = SKU
        fields = (
            "id",
            "name",
            "price",
            "discount",
            "image",
            "active_quantity",
            "characteristics",
        )


class B2CProductImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImage
        fields = ("url", "ordering")


class B2CProductCharacteristicSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductCharacteristic
        fields = ("name", "value")


class B2CProductSerializer(serializers.ModelSerializer):
    category = B2CCategorySerializer(read_only=True)
    images = B2CProductImageSerializer(source="image_rows", many=True, read_only=True)
    characteristics = B2CProductCharacteristicSerializer(
        source="characteristic_rows", many=True, read_only=True
    )
    skus = B2CSKUSerializer(many=True, read_only=True)

    class Meta:
        model = Product
        fields = (
            "id",
            "title",
            "description",
            "status",
            "category",
            "images",
            "characteristics",
            "skus",
        )
