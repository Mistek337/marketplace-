from django.db import transaction
from django.http import Http404
from uuid import UUID
from rest_framework import generics, status
from rest_framework import permissions
from rest_framework.response import Response
from django.conf import settings
from django.db.models import Min

from sellers.auth import SellerJWTAuthentication

from .models import Category, Product, SKU, SKUImage
from .public_catalog import public_detail_queryset
from .moderation_client import emit_product_created_event, emit_product_edited_event
from .api_errors import (
    FORBIDDEN,
    NOT_FOUND,
    UNAUTHORIZED,
    drf_validation_error,
    error_body,
)
from .serializers import (
    CategoryCreateSerializer,
    CategoryFlatSerializer,
    CategoryUpdateSerializer,
    CategoryWithChildrenResponseSerializer,
    ProductMyListItemSerializer,
    ProductCreateSerializer,
    ProductResponseSerializer,
    ProductPublicResponseSerializer,
    ProductShortResponseSerializer,
    ProductUpdateSerializer,
    SKUCreateSerializer,
    SKUResponseSerializer,
    SKUUpdateSerializer,
)


def _valid_service_key(request) -> bool:
    service_key = request.headers.get("X-Service-Key")
    if not service_key:
        return False
    b2c_key = getattr(settings, "B2C_TO_B2B_KEY", "") or ""
    moderation_key = getattr(settings, "MODERATION_TO_B2B_KEY", "") or ""
    return service_key in {k for k in (b2c_key, moderation_key) if k}


def _product_forbidden_response() -> Response:
    return Response(
        error_body(code=FORBIDDEN, message="Product not found"),
        status=status.HTTP_403_FORBIDDEN,
    )


def _product_not_found_response() -> Response:
    return Response(
        error_body(code=NOT_FOUND, message="Product not found"),
        status=status.HTTP_404_NOT_FOUND,
    )


def _transition_product_to_moderation_on_edit(product: Product) -> bool:
    """MODERATED/BLOCKED → ON_MODERATION после правки (OpenAPI updateProduct/updateSku)."""
    if product.status not in (Product.Status.MODERATED, Product.Status.BLOCKED):
        return False
    product.status = Product.Status.ON_MODERATION
    product.save(update_fields=["status", "updated_at"])
    return True


class CategoryListAPIView(generics.ListCreateAPIView):
    """GET /api/categories — список, POST /api/categories — создание."""

    authentication_classes = [SellerJWTAuthentication]
    queryset = Category.objects.all().order_by("id")

    def get_permissions(self):
        if self.request.method == "POST":
            return [permissions.IsAuthenticated()]
        return [permissions.AllowAny()]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return CategoryCreateSerializer
        return CategoryFlatSerializer

    def get_queryset(self):
        qs = Category.objects.all().order_by("id")
        parent_id = self.request.query_params.get("parent_id")
        only_root = self.request.query_params.get("only_root")

        if only_root is not None and str(only_root).lower() in ("1", "true", "yes"):
            qs = qs.filter(parent__isnull=True)
        elif parent_id:
            qs = qs.filter(parent_id=parent_id)

        return qs

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        category = serializer.save()
        out = CategoryWithChildrenResponseSerializer(category)
        return Response(out.data, status=status.HTTP_201_CREATED)


class CategoryDetailAPIView(generics.RetrieveUpdateAPIView):
    authentication_classes = [SellerJWTAuthentication]
    queryset = Category.objects.prefetch_related("children").all()
    serializer_class = CategoryWithChildrenResponseSerializer
    lookup_field = "id"

    def get_permissions(self):
        if self.request.method in ("PATCH", "DELETE"):
            return [permissions.IsAuthenticated()]
        return [permissions.AllowAny()]

    def get_serializer_class(self):
        if self.request.method == "PATCH":
            return CategoryUpdateSerializer
        return CategoryWithChildrenResponseSerializer

    def patch(self, request, *args, **kwargs):
        kwargs["partial"] = True
        return self.update(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        category = serializer.save()
        return Response(
            CategoryWithChildrenResponseSerializer(category).data,
            status=status.HTTP_200_OK,
        )

    def delete(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ProductListCreateAPIView(generics.ListCreateAPIView):
    """GET /api/v1/products/ — список; POST /api/v1/products/ — создать карточку (status CREATED)."""

    authentication_classes = [SellerJWTAuthentication]
    queryset = Product.objects.select_related('category').prefetch_related(
        'image_rows',
        'characteristic_rows',
        'skus__characteristic_rows',
        'skus__image_rows',
    )

    def get_permissions(self):
        if self.request.method == 'POST':
            return [permissions.IsAuthenticated()]
        return [permissions.AllowAny()]

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return ProductCreateSerializer
        return ProductShortResponseSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                drf_validation_error(serializer.errors),
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        product = serializer.save()
        out = ProductResponseSerializer(product)
        return Response(out.data, status=status.HTTP_201_CREATED)

    def list(self, request, *args, **kwargs):
        if not request.user or not getattr(request.user, "is_authenticated", False):
            return Response(
                error_body(code=UNAUTHORIZED, message="Authentication required"),
                status=status.HTTP_401_UNAUTHORIZED,
            )

        try:
            limit = int(request.query_params.get("limit", 20))
            offset = int(request.query_params.get("offset", 0))
        except ValueError:
            return Response(
                drf_validation_error(
                    {"limit": "Invalid pagination parameters"},
                ),
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        limit = max(1, min(limit, 100))
        offset = max(0, offset)

        qs = (
            Product.objects.filter(seller_id=request.user.id)
            .prefetch_related("image_rows", "skus")
            .annotate(min_price=Min("skus__price"))
            .order_by("-created_at")
        )
        include_deleted = str(
            request.query_params.get("include_deleted", "false")
        ).lower() in ("1", "true", "yes")
        if not include_deleted:
            qs = qs.filter(deleted=False)

        status_filter = request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter)

        total_count = qs.count()
        items = qs[offset : offset + limit]
        return Response(
            {
                "items": ProductShortResponseSerializer(items, many=True).data,
                "total_count": total_count,
                "limit": limit,
                "offset": offset,
            },
            status=status.HTTP_200_OK,
        )


class ProductMyListAPIView(generics.ListAPIView):
    authentication_classes = [SellerJWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ProductMyListItemSerializer

    def get_queryset(self):
        return Product.objects.filter(seller_id=self.request.user.id).order_by("-created_at")

    def list(self, request, *args, **kwargs):
        try:
            limit = int(request.query_params.get("limit", 20))
            offset = int(request.query_params.get("offset", 0))
        except ValueError:
            return Response(
                {"detail": [{"msg": "Invalid pagination parameters"}]},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        limit = max(1, limit)
        offset = max(0, offset)

        qs = self.get_queryset()
        total = qs.count()
        items = qs[offset : offset + limit]
        return Response(
            {"total": total, "items": ProductMyListItemSerializer(items, many=True).data},
            status=status.HTTP_200_OK,
        )


class ProductRetrieveUpdateAPIView(generics.RetrieveUpdateAPIView):
    """GET / PATCH /api/v1/products/{id} — OpenAPI seller-view / public-view."""

    authentication_classes = [SellerJWTAuthentication]
    queryset = Product.objects.select_related('category').prefetch_related(
        'image_rows',
        'characteristic_rows',
        'skus__characteristic_rows',
        'skus__image_rows',
    )
    lookup_field = 'pk'

    def get_serializer_class(self):
        if self.request.method == 'PATCH':
            return ProductUpdateSerializer
        return ProductResponseSerializer

    def put(self, request, *args, **kwargs):
        return Response(status=status.HTTP_405_METHOD_NOT_ALLOWED)

    def _resolve_product(self, request, raw_id: str) -> Product | None:
        try:
            product_id = UUID(str(raw_id))
        except (TypeError, ValueError):
            return None

        product = self.get_queryset().filter(id=product_id).first()
        if product is None:
            return None

        seller_id = getattr(request.user, "id", None)
        is_owner = (
            request.user
            and getattr(request.user, "is_authenticated", False)
            and seller_id is not None
            and product.seller_id == seller_id
        )
        if is_owner:
            return product
        service_key = request.headers.get("X-Service-Key")
        b2c_key = getattr(settings, "B2C_TO_B2B_KEY", "") or ""
        if b2c_key and service_key == b2c_key:
            return public_detail_queryset().filter(id=product_id).first()
        if _valid_service_key(request):
            return product
        return None

    def get(self, request, *args, **kwargs):
        product = self._resolve_product(request, kwargs.get("pk", ""))
        if product is None:
            return _product_not_found_response()

        seller_id = getattr(request.user, "id", None)
        is_owner = (
            request.user
            and getattr(request.user, "is_authenticated", False)
            and seller_id is not None
            and product.seller_id == seller_id
        )
        if is_owner:
            return Response(
                ProductResponseSerializer(product).data,
                status=status.HTTP_200_OK,
            )
        return Response(
            ProductPublicResponseSerializer(product).data,
            status=status.HTTP_200_OK,
        )

    def patch(self, request, *args, **kwargs):
        if not request.user or not getattr(request.user, "is_authenticated", False):
            return _product_not_found_response()

        product = self._resolve_product(request, kwargs.get("pk", ""))
        if product is None:
            return _product_not_found_response()

        seller_id = getattr(request.user, "id", None)
        if product.seller_id != seller_id:
            return _product_forbidden_response()

        if product.status == Product.Status.HARD_BLOCKED:
            return Response(
                error_body(code=FORBIDDEN, message="Product is hard-blocked"),
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = ProductUpdateSerializer(product, data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(
                drf_validation_error(serializer.errors),
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        emit_edited = False
        with transaction.atomic():
            product = Product.objects.select_for_update().get(pk=product.pk)
            product = serializer.save()
            if _transition_product_to_moderation_on_edit(product):
                emit_edited = True

        if emit_edited:
            emit_product_edited_event(product_id=product.id, seller_id=product.seller_id)

        return Response(
            ProductResponseSerializer(product).data,
            status=status.HTTP_200_OK,
        )


class SKUCreateAPIView(generics.CreateAPIView):
    """POST /api/v1/skus/ — OpenAPI createSku."""

    authentication_classes = [SellerJWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]
    queryset = SKU.objects.select_related('product').prefetch_related(
        'characteristic_rows',
        'image_rows',
    )
    serializer_class = SKUCreateSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                drf_validation_error(serializer.errors),
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        data = serializer.validated_data
        seller_id = getattr(request.user, "id", None)
        emit_after_commit = False
        emit_product_id = None
        emit_seller_id = None

        with transaction.atomic():
            product = Product.objects.select_for_update().filter(id=data["product_id"]).first()
            if product is None or product.seller_id != seller_id:
                return _product_forbidden_response()

            if product.status == Product.Status.HARD_BLOCKED:
                return Response(
                    error_body(
                        code=FORBIDDEN,
                        message="Cannot add SKU to hard-blocked product",
                    ),
                    status=status.HTTP_403_FORBIDDEN,
                )

            had_skus = SKU.objects.filter(product=product).exists()
            characteristics_data = data.get("characteristics", [])
            images_data = data.get("images", [])
            sku = SKU.objects.create(
                product=product,
                name=data["name"],
                price=data["price"],
                cost_price=data.get("cost_price"),
                discount=data.get("discount", 0),
                article=data.get("article"),
                active_quantity=0,
                reserved_quantity=0,
            )
            for row in images_data:
                SKUImage.objects.create(sku=sku, **row)
            for row in characteristics_data:
                sku.characteristic_rows.create(**row)

            if not had_skus and product.status == Product.Status.CREATED:
                product.status = Product.Status.ON_MODERATION
                product.save(update_fields=["status", "updated_at"])
                emit_after_commit = True
                emit_product_id = product.id
                emit_seller_id = product.seller_id

        if emit_after_commit:
            emit_product_created_event(
                product_id=emit_product_id,
                seller_id=emit_seller_id,
            )

        sku.refresh_from_db()
        return Response(
            SKUResponseSerializer(sku).data,
            status=status.HTTP_201_CREATED,
        )


class SKURetrieveUpdateAPIView(generics.RetrieveUpdateAPIView):
    """GET / PATCH /api/v1/skus/{id} — OpenAPI getSku / updateSku."""

    authentication_classes = [SellerJWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]
    queryset = SKU.objects.select_related('product').prefetch_related(
        'characteristic_rows',
        'image_rows',
    )
    lookup_field = 'pk'

    def get_queryset(self):
        return super().get_queryset().filter(product__seller_id=self.request.user.id)

    def get_serializer_class(self):
        if self.request.method == 'PATCH':
            return SKUUpdateSerializer
        return SKUResponseSerializer

    def put(self, request, *args, **kwargs):
        return Response(status=status.HTTP_405_METHOD_NOT_ALLOWED)

    def get(self, request, *args, **kwargs):
        try:
            sku = self.get_object()
        except Http404:
            return Response(
                error_body(code=NOT_FOUND, message="SKU not found"),
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(
            SKUResponseSerializer(sku).data,
            status=status.HTTP_200_OK,
        )

    def patch(self, request, *args, **kwargs):
        try:
            sku = self.get_object()
        except Http404:
            return Response(
                error_body(code=FORBIDDEN, message="SKU not found"),
                status=status.HTTP_403_FORBIDDEN,
            )

        if sku.product.status == Product.Status.HARD_BLOCKED:
            return Response(
                error_body(code=FORBIDDEN, message="Product is hard-blocked"),
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = SKUUpdateSerializer(sku, data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(
                drf_validation_error(serializer.errors),
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        emit_edited = False
        with transaction.atomic():
            sku = SKU.objects.select_for_update().select_related("product").get(pk=sku.pk)
            product = Product.objects.select_for_update().get(pk=sku.product_id)
            sku = serializer.save()
            if _transition_product_to_moderation_on_edit(product):
                emit_edited = True

        if emit_edited:
            emit_product_edited_event(product_id=product.id, seller_id=product.seller_id)

        sku.refresh_from_db()
        return Response(
            SKUResponseSerializer(sku).data,
            status=status.HTTP_200_OK,
        )
