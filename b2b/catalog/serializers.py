from rest_framework import serializers

from .openapi_patch import _NOT_PROVIDED, is_patch_null, pop_patch_value
from .models import (
    Category,
    Product,
    ProductCharacteristic,
    ProductImage,
    SKU,
    SKUCharacteristic,
    SKUImage,
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


class ProductCharacteristicSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductCharacteristic
        fields = ('id', 'name', 'value')


class CharacteristicResponseSerializer(ProductCharacteristicSerializer):
    """OpenAPI CharacteristicResponse (product characteristics)."""


class SKUImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = SKUImage
        fields = ('id', 'url', 'ordering')


class SKUResponseSerializer(serializers.ModelSerializer):
    """OpenAPI SKUResponse — seller view."""

    product_id = serializers.UUIDField(read_only=True)
    stock_quantity = serializers.IntegerField(read_only=True)
    cost_price = serializers.IntegerField(allow_null=True, read_only=True)
    article = serializers.CharField(allow_null=True, read_only=True)
    images = SKUImageSerializer(source='image_rows', many=True, read_only=True)
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


class SKUPublicResponseSerializer(serializers.ModelSerializer):
    """OpenAPI SKUPublicResponse — витрина B2C."""

    product_id = serializers.UUIDField(read_only=True)
    stock_quantity = serializers.IntegerField(read_only=True)
    article = serializers.CharField(allow_null=True, read_only=True)
    images = SKUImageSerializer(source='image_rows', many=True, read_only=True)
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
            'stock_quantity',
            'active_quantity',
            'article',
            'images',
            'characteristics',
        )


class ProductDetailSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)
    category_id = serializers.UUIDField(read_only=True)
    images = ProductImageSerializer(source='image_rows', many=True, read_only=True)
    characteristics = ProductCharacteristicSerializer(
        source='characteristic_rows',
        many=True,
        read_only=True,
    )
    skus = SKUResponseSerializer(many=True, read_only=True)
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
    moderator_comment = serializers.SerializerMethodField()
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

    def get_moderator_comment(self, obj: Product) -> str | None:
        comment = (obj.moderator_comment or "").strip()
        return comment or None


class ProductPublicResponseSerializer(serializers.ModelSerializer):
    """OpenAPI ProductPublicResponse — GET с X-Service-Key (без seller-only полей у SKU)."""

    category_id = serializers.UUIDField(read_only=True)
    images = ProductImageSerializer(source='image_rows', many=True, read_only=True)
    characteristics = CharacteristicResponseSerializer(
        source='characteristic_rows',
        many=True,
        read_only=True,
    )
    skus = SKUPublicResponseSerializer(many=True, read_only=True)

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
            'images',
            'characteristics',
            'skus',
            'created_at',
            'updated_at',
        )


class ProductRefWriteSerializer(serializers.Serializer):
    """Ссылка на существующий товар при создании SKU."""

    id = serializers.PrimaryKeyRelatedField(queryset=Product.objects.all())


class SKUImageCreateSerializer(serializers.Serializer):
    url = serializers.CharField(max_length=2048)
    ordering = serializers.IntegerField(default=0, required=False, min_value=0)


class SKUCreateSerializer(serializers.Serializer):
    """POST /api/v1/skus — OpenAPI SKUCreate."""

    product_id = serializers.UUIDField()
    name = serializers.CharField(max_length=255)
    price = serializers.IntegerField(min_value=0)
    discount = serializers.IntegerField(required=False, default=0, min_value=0)
    cost_price = serializers.IntegerField(required=False, allow_null=True, min_value=0)
    article = serializers.CharField(required=False, allow_blank=True, max_length=255, default="")
    images = SKUImageCreateSerializer(many=True, required=False, default=list)
    characteristics = CharacteristicWriteSerializer(many=True, required=False, default=list)

    def validate(self, attrs: dict) -> dict:
        name = (attrs.get('name') or '').strip()
        if not name:
            raise serializers.ValidationError({'name': 'name is required'})
        attrs['name'] = name

        price = attrs.get('price')
        if price is None:
            raise serializers.ValidationError({'price': 'This field is required.'})
        attrs['price'] = int(price)
        if attrs['price'] < 0:
            raise serializers.ValidationError({'price': 'price must be >= 0 (kopecks)'})

        cost_price = attrs.get('cost_price')
        if cost_price is not None:
            cost_price = int(cost_price)
            if cost_price < 0:
                raise serializers.ValidationError(
                    {'cost_price': 'cost_price must be >= 0 (kopecks)'}
                )
            attrs['cost_price'] = cost_price

        discount = attrs.get('discount', 0)
        if discount is None or int(discount) < 0:
            raise serializers.ValidationError(
                {'discount': 'discount must be a non-negative integer (kopecks)'}
            )
        attrs['discount'] = int(discount)

        article = (attrs.get('article') or '').strip()
        attrs['article'] = article or None
        return attrs


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


class ProductUpdateSerializer(serializers.Serializer):
    """PATCH /api/v1/products/{id} — OpenAPI ProductUpdate (все поля опциональны)."""

    title = serializers.CharField(
        required=False,
        allow_null=True,
        allow_blank=False,
        max_length=255,
    )
    description = serializers.CharField(required=False, allow_null=True, max_length=5000)
    category_id = serializers.UUIDField(required=False, allow_null=True)
    characteristics = CharacteristicWriteSerializer(many=True, required=False, allow_null=True)

    def validate(self, attrs: dict) -> dict:
        title = pop_patch_value(attrs, 'title')
        if title is not _NOT_PROVIDED:
            if is_patch_null(title):
                raise serializers.ValidationError({'title': 'title cannot be null'})
            attrs['title'] = title

        description = pop_patch_value(attrs, 'description')
        if description is not _NOT_PROVIDED:
            attrs['description'] = '' if is_patch_null(description) else description

        category_id = pop_patch_value(attrs, 'category_id')
        if category_id is not _NOT_PROVIDED:
            if is_patch_null(category_id):
                raise serializers.ValidationError({'category_id': 'category_id cannot be null'})
            if not Category.objects.filter(pk=category_id).exists():
                raise serializers.ValidationError({'category_id': 'Category not found'})
            attrs['category_id'] = category_id

        characteristics = pop_patch_value(attrs, 'characteristics')
        if characteristics is not _NOT_PROVIDED:
            if is_patch_null(characteristics):
                attrs['_characteristics'] = None
            else:
                attrs['_characteristics'] = characteristics

        return attrs

    def update(self, instance: Product, validated_data: dict) -> Product:
        characteristics_data = validated_data.pop('_characteristics', _NOT_PROVIDED)

        if 'title' in validated_data:
            instance.title = validated_data['title']
        if 'description' in validated_data:
            instance.description = validated_data['description']
        if 'category_id' in validated_data:
            instance.category_id = validated_data['category_id']

        instance.save()

        if characteristics_data is not _NOT_PROVIDED:
            instance.characteristic_rows.all().delete()
            if characteristics_data:
                for row in characteristics_data:
                    ProductCharacteristic.objects.create(product=instance, **row)

        return instance

    def to_representation(self, instance: Product) -> dict:
        return ProductResponseSerializer(instance, context=self.context).data


class SKUUpdateSerializer(serializers.Serializer):
    """PATCH /api/v1/skus/{id} — OpenAPI SKUUpdate (все поля опциональны)."""

    name = serializers.CharField(required=False, allow_null=True, max_length=255)
    price = serializers.IntegerField(required=False, allow_null=True, min_value=0)
    discount = serializers.IntegerField(required=False, allow_null=True, min_value=0)
    cost_price = serializers.IntegerField(required=False, allow_null=True, min_value=0)
    article = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    characteristics = CharacteristicWriteSerializer(many=True, required=False, allow_null=True)

    def validate(self, attrs: dict) -> dict:
        name = pop_patch_value(attrs, 'name')
        if name is not _NOT_PROVIDED:
            if is_patch_null(name):
                raise serializers.ValidationError({'name': 'name cannot be null'})
            name = (name or '').strip()
            if not name:
                raise serializers.ValidationError({'name': 'name cannot be empty'})
            attrs['name'] = name

        for field in ('price', 'discount'):
            value = pop_patch_value(attrs, field)
            if value is not _NOT_PROVIDED:
                if is_patch_null(value):
                    raise serializers.ValidationError({field: f'{field} cannot be null'})
                attrs[field] = int(value)

        cost_price = pop_patch_value(attrs, 'cost_price')
        if cost_price is not _NOT_PROVIDED:
            if is_patch_null(cost_price):
                attrs['cost_price'] = None
            else:
                attrs['cost_price'] = int(cost_price)

        article = pop_patch_value(attrs, 'article')
        if article is not _NOT_PROVIDED:
            if is_patch_null(article):
                attrs['article'] = None
            else:
                attrs['article'] = (article or '').strip() or None

        characteristics = pop_patch_value(attrs, 'characteristics')
        if characteristics is not _NOT_PROVIDED:
            if is_patch_null(characteristics):
                attrs['_characteristics'] = None
            else:
                attrs['_characteristics'] = characteristics

        return attrs

    def update(self, instance: SKU, validated_data: dict) -> SKU:
        characteristics_data = validated_data.pop('_characteristics', _NOT_PROVIDED)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if characteristics_data is not _NOT_PROVIDED:
            instance.characteristic_rows.all().delete()
            if characteristics_data:
                for row in characteristics_data:
                    SKUCharacteristic.objects.create(sku=instance, **row)

        return instance

    def to_representation(self, instance: SKU) -> dict:
        return SKUResponseSerializer(instance, context=self.context).data


class ProductShortResponseSerializer(serializers.ModelSerializer):
    """OpenAPI ProductShortResponse — GET /api/v1/products (seller list)."""

    category_id = serializers.UUIDField(read_only=True)
    min_price = serializers.SerializerMethodField()
    cover_image = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = (
            "id",
            "title",
            "slug",
            "status",
            "category_id",
            "deleted",
            "created_at",
            "min_price",
            "cover_image",
        )

    def get_min_price(self, obj: Product) -> int | None:
        annotated = getattr(obj, "min_price", None)
        if annotated is not None:
            return int(annotated)
        prices = [int(s.price) for s in obj.skus.all() if s.price is not None]
        return min(prices) if prices else None

    def get_cover_image(self, obj: Product) -> str | None:
        images = list(obj.image_rows.all())
        if not images:
            return None
        return images[0].url


class ProductPublicShortResponseSerializer(serializers.ModelSerializer):
    """OpenAPI ProductPublicShortResponse — GET /api/v1/public/products."""

    category_id = serializers.UUIDField(read_only=True)
    min_price = serializers.SerializerMethodField()
    cover_image = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = (
            "id",
            "title",
            "slug",
            "status",
            "category_id",
            "min_price",
            "cover_image",
            "created_at",
        )

    def get_min_price(self, obj: Product) -> int:
        annotated = getattr(obj, "min_price", None)
        if annotated is not None:
            return int(annotated)
        prices = [int(s.price) for s in obj.skus.all() if s.price is not None]
        return min(prices) if prices else 0

    def get_cover_image(self, obj: Product) -> str | None:
        images = list(obj.image_rows.all())
        if not images:
            return None
        return images[0].url


class PublicProductBatchRequestSerializer(serializers.Serializer):
    product_ids = serializers.ListField(
        child=serializers.UUIDField(),
        allow_empty=False,
        max_length=100,
    )


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


class B2CSKUSerializer(SKUPublicResponseSerializer):
    """Алиас для витрины B2C."""


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
