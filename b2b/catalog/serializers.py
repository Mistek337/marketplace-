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


class SKUCharacteristicSerializer(serializers.ModelSerializer):
    class Meta:
        model = SKUCharacteristic
        fields = ('name', 'value')


class SKUSerializer(serializers.ModelSerializer):
    activeQuantity = serializers.IntegerField(source='active_quantity', read_only=True)
    discount = serializers.IntegerField(read_only=True)
    image = serializers.CharField(read_only=True, allow_null=True)
    characteristics = SKUCharacteristicSerializer(
        source='characteristic_rows',
        many=True,
        read_only=True,
    )

    class Meta:
        model = SKU
        fields = (
            'id',
            'name',
            'price',
            'discount',
            'image',
            'activeQuantity',
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

    class Meta:
        model = Product
        fields = (
            'id',
            'seller_id',
            'category_id',
            'title',
            'description',
            'status',
            'category',
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

    product = ProductRefWriteSerializer()
    activeQuantity = serializers.IntegerField(source='active_quantity')
    discount = serializers.IntegerField(required=False, default=0, min_value=0)
    image = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    characteristics = SKUCharacteristicSerializer(many=True, required=False)

    class Meta:
        model = SKU
        fields = (
            'product',
            'name',
            'price',
            'discount',
            'image',
            'activeQuantity',
            'characteristics',
        )

    def create(self, validated_data: dict) -> SKU:
        product = validated_data.pop('product')['id']
        characteristics_data = validated_data.pop('characteristics', [])
        sku = SKU.objects.create(product=product, **validated_data)
        for ch in characteristics_data:
            SKUCharacteristic.objects.create(sku=sku, **ch)
        return sku

    def to_representation(self, instance: SKU) -> dict:
        return SKUSerializer(instance, context=self.context).data


class ProductCreateSerializer(serializers.ModelSerializer):
    """
    POST /api/v1/products — только карточка товара (без SKU).
    Статус всегда UNMODERATED (поле status из запроса не используется).
    """

    category_id = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all(),
        source='category',
    )
    images = ProductImageSerializer(many=True, required=False)
    characteristics = ProductCharacteristicSerializer(many=True, required=False)

    class Meta:
        model = Product
        fields = ('title', 'description', 'category_id', 'images', 'characteristics')

    def create(self, validated_data: dict) -> Product:
        category = validated_data.pop('category')
        images_data = validated_data.pop('images', [])
        characteristics_data = validated_data.pop('characteristics', [])
        request = self.context.get('request')

        product = Product.objects.create(
            **validated_data,
            category=category,
            seller_id=getattr(getattr(request, "user", None), "id", None),
            status=Product.Status.CREATED,
        )

        for row in images_data:
            ProductImage.objects.create(product=product, **row)
        for row in characteristics_data:
            ProductCharacteristic.objects.create(product=product, **row)

        return product

    def to_representation(self, instance: Product) -> dict:
        return ProductDetailSerializer(instance, context=self.context).data


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

    activeQuantity = serializers.IntegerField(source='active_quantity', required=False)
    discount = serializers.IntegerField(required=False, min_value=0)
    image = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    characteristics = SKUCharacteristicSerializer(many=True, required=False)

    class Meta:
        model = SKU
        fields = ('name', 'price', 'discount', 'image', 'activeQuantity', 'characteristics')
        extra_kwargs = {
            'name': {'required': False},
            'price': {'required': False},
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
