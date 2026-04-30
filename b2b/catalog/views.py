from rest_framework import generics, status
from rest_framework import permissions
from rest_framework.response import Response
from django.conf import settings
from django.db.models import Exists, OuterRef, Q, Min

from sellers.auth import SellerJWTAuthentication

from .models import Category, Product, SKU
from .serializers import (
    B2CProductSerializer,
    CategoryCreateSerializer,
    CategoryFlatSerializer,
    CategoryUpdateSerializer,
    CategoryWithChildrenResponseSerializer,
    ProductMyListItemSerializer,
    ProductCreateSerializer,
    ProductDetailSerializer,
    ProductListSerializer,
    ProductUpdateSerializer,
    SKUCreateSerializer,
    SKUSerializer,
    SKUUpdateSerializer,
)


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
    """GET /api/v1/products/ — список; POST /api/v1/products/ — создать (статус UNMODERATED)."""

    authentication_classes = [SellerJWTAuthentication]
    queryset = Product.objects.select_related('category').prefetch_related(
        'image_rows',
        'characteristic_rows',
        'skus__characteristic_rows',
    )

    def get_permissions(self):
        if self.request.method == 'POST':
            return [permissions.IsAuthenticated()]
        return [permissions.AllowAny()]

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return ProductCreateSerializer
        return ProductListSerializer

    def list(self, request, *args, **kwargs):
        service_key = request.headers.get("X-Service-Key")
        expected = getattr(settings, "B2C_TO_B2B_KEY", "")
        if not expected or service_key != expected:
            return Response(status=status.HTTP_403_FORBIDDEN)

        try:
            limit = int(request.query_params.get("limit", 20))
            offset = int(request.query_params.get("offset", 0))
        except ValueError:
            return Response(
                {"detail": [{"msg": "Invalid pagination parameters"}]},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        limit = max(1, min(limit, 100))
        offset = max(0, offset)

        qs = Product.objects.select_related("category").prefetch_related(
            "image_rows",
            "characteristic_rows",
            "skus__characteristic_rows",
        )

        # Visibility for B2C catalog
        visible_sku_qs = SKU.objects.filter(product_id=OuterRef("pk"), active_quantity__gt=0)
        qs = qs.annotate(has_stock=Exists(visible_sku_qs)).filter(
            status=Product.Status.MODERATED,
            deleted=False,
            has_stock=True,
        )

        category = request.query_params.get("category")
        if category:
            qs = qs.filter(category_id=category)

        search = request.query_params.get("search")
        if search:
            qs = qs.filter(Q(title__icontains=search) | Q(description__icontains=search))

        ids = request.query_params.get("ids")
        if ids:
            raw_ids = [x.strip() for x in ids.split(",") if x.strip()]
            qs = qs.filter(id__in=raw_ids)

        sort = request.query_params.get("sort")
        if sort in ("price_asc", "price_desc"):
            qs = qs.annotate(min_price=Min("skus__price"))
            qs = qs.order_by("min_price" if sort == "price_asc" else "-min_price")
        elif sort == "date_desc":
            qs = qs.order_by("-created_at")
        else:
            qs = qs.order_by("-created_at")

        total_count = qs.count()
        items = qs[offset : offset + limit]
        return Response(
            {
                "items": B2CProductSerializer(items, many=True).data,
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
    """GET / PUT /api/v1/products/{id} — товар со SKU; обновление карточки (частичный PUT, без статуса в теле)."""

    queryset = Product.objects.select_related('category').prefetch_related(
        'image_rows',
        'characteristic_rows',
        'skus__characteristic_rows',
    )
    lookup_field = 'pk'

    def get_serializer_class(self):
        if self.request.method == 'PUT':
            return ProductUpdateSerializer
        return ProductDetailSerializer

    def put(self, request, *args, **kwargs):
        kwargs['partial'] = True
        return self.update(request, *args, **kwargs)

    def patch(self, request, *args, **kwargs):
        return Response(status=status.HTTP_405_METHOD_NOT_ALLOWED)


class SKUCreateAPIView(generics.CreateAPIView):
    """POST /api/v1/skus/ — создать SKU для товара."""

    queryset = SKU.objects.select_related('product').prefetch_related('characteristic_rows')
    serializer_class = SKUCreateSerializer


class SKURetrieveUpdateAPIView(generics.RetrieveUpdateAPIView):
    """GET / PUT /api/v1/skus/{id} — один SKU; обновление (частичный PUT)."""

    queryset = SKU.objects.select_related('product').prefetch_related('characteristic_rows')
    lookup_field = 'pk'

    def get_serializer_class(self):
        if self.request.method == 'PUT':
            return SKUUpdateSerializer
        return SKUSerializer

    def put(self, request, *args, **kwargs):
        kwargs['partial'] = True
        return self.update(request, *args, **kwargs)

    def patch(self, request, *args, **kwargs):
        return Response(status=status.HTTP_405_METHOD_NOT_ALLOWED)
