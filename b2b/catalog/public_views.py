from uuid import UUID

from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .api_errors import NOT_FOUND, drf_validation_error, error_body
from .public_catalog import (
    parse_pagination,
    parse_similar_limit,
    public_detail_queryset,
    public_list_queryset,
    public_similar_queryset,
    public_visible_sku_queryset,
    require_b2c_service_key,
)
from .serializers import (
    ProductPublicResponseSerializer,
    ProductPublicShortResponseSerializer,
    PublicProductBatchRequestSerializer,
    SKUPublicResponseSerializer,
)


class PublicProductListAPIView(APIView):
    """GET /api/v1/public/products — OpenAPI listPublicProducts."""

    permission_classes = [permissions.AllowAny]

    def get(self, request):
        denied = require_b2c_service_key(request)
        if denied is not None:
            return denied

        pagination = parse_pagination(request)
        if isinstance(pagination, Response):
            return pagination
        limit, offset = pagination

        qs = public_list_queryset(request)
        if isinstance(qs, Response):
            return qs

        total_count = qs.count()
        items = qs[offset : offset + limit]
        return Response(
            {
                "items": ProductPublicShortResponseSerializer(items, many=True).data,
                "total_count": total_count,
                "limit": limit,
                "offset": offset,
            },
            status=status.HTTP_200_OK,
        )


class PublicProductBatchAPIView(APIView):
    """POST /api/v1/public/products/batch — OpenAPI batchPublicProducts."""

    permission_classes = [permissions.AllowAny]

    def post(self, request):
        denied = require_b2c_service_key(request)
        if denied is not None:
            return denied

        serializer = PublicProductBatchRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                drf_validation_error(serializer.errors),
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        product_ids = serializer.validated_data["product_ids"]
        qs = (
            public_detail_queryset()
            .filter(id__in=product_ids)
            .order_by("id")
        )
        return Response(
            ProductPublicResponseSerializer(qs, many=True).data,
            status=status.HTTP_200_OK,
        )


class PublicProductRetrieveAPIView(APIView):
    """GET /api/v1/public/products/{product_id} — OpenAPI getPublicProduct."""

    permission_classes = [permissions.AllowAny]

    def get(self, request, product_id):
        denied = require_b2c_service_key(request)
        if denied is not None:
            return denied

        try:
            UUID(str(product_id))
        except (TypeError, ValueError):
            return Response(
                error_body(code=NOT_FOUND, message="Product not found"),
                status=status.HTTP_404_NOT_FOUND,
            )

        product = public_detail_queryset().filter(id=product_id).first()
        if product is None:
            return Response(
                error_body(code=NOT_FOUND, message="Product not found"),
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(
            ProductPublicResponseSerializer(product).data,
            status=status.HTTP_200_OK,
        )


class PublicProductSimilarAPIView(APIView):
    """GET /api/v1/public/products/{product_id}/similar — OpenAPI getPublicSimilarProducts."""

    permission_classes = [permissions.AllowAny]

    def get(self, request, product_id):
        denied = require_b2c_service_key(request)
        if denied is not None:
            return denied

        try:
            UUID(str(product_id))
        except (TypeError, ValueError):
            return Response(
                error_body(code=NOT_FOUND, message="Product not found"),
                status=status.HTTP_404_NOT_FOUND,
            )

        limit = parse_similar_limit(request)
        if isinstance(limit, Response):
            return limit

        items = public_similar_queryset(product_id=product_id, limit=limit)
        if items is None:
            return Response(
                error_body(code=NOT_FOUND, message="Product not found"),
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(
            ProductPublicShortResponseSerializer(items, many=True).data,
            status=status.HTTP_200_OK,
        )


class PublicSKURetrieveAPIView(APIView):
    """GET /api/v1/public/skus/{sku_id} — OpenAPI getPublicSku."""

    permission_classes = [permissions.AllowAny]

    def get(self, request, sku_id):
        denied = require_b2c_service_key(request)
        if denied is not None:
            return denied

        try:
            UUID(str(sku_id))
        except (TypeError, ValueError):
            return Response(
                error_body(code=NOT_FOUND, message="SKU not found"),
                status=status.HTTP_404_NOT_FOUND,
            )

        sku = public_visible_sku_queryset().filter(id=sku_id).first()
        if sku is None:
            return Response(
                error_body(code=NOT_FOUND, message="SKU not found"),
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(
            SKUPublicResponseSerializer(sku).data,
            status=status.HTTP_200_OK,
        )
