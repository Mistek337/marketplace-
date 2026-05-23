"""POST /api/v1/inventory/reserve и /unreserve — B2C checkout."""

from __future__ import annotations

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .api_errors import drf_validation_error
from .inventory_serializers import InventoryOrderRequestSerializer, ReserveRequestSerializer
from .inventory_service import (
    InventoryConflict,
    InventoryItemInput,
    InventoryNotFound,
    conflict_error_response,
    not_found_error_response,
    notify_out_of_stock,
    reserve_inventory,
    unreserve_inventory,
)
from .public_catalog import require_b2c_service_key


class ReserveInventoryAPIView(APIView):
    """OpenAPI reserveInventory — all-or-nothing, idempotency_key TTL 1ч."""

    def post(self, request, *args, **kwargs):
        denied = require_b2c_service_key(request)
        if denied is not None:
            return denied

        serializer = ReserveRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                drf_validation_error(serializer.errors),
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        data = serializer.validated_data
        items = [
            InventoryItemInput(sku_id=row["sku_id"], quantity=row["quantity"])
            for row in data["items"]
        ]

        try:
            response_body, out_of_stock = reserve_inventory(
                idempotency_key=data["idempotency_key"],
                order_id=data["order_id"],
                items=items,
            )
        except InventoryConflict as exc:
            return conflict_error_response(exc)

        notify_out_of_stock(out_of_stock)
        return Response(response_body, status=status.HTTP_200_OK)


class UnreserveInventoryAPIView(APIView):
    """OpenAPI unreserveInventory — идемпотентно по order_id."""

    def post(self, request, *args, **kwargs):
        denied = require_b2c_service_key(request)
        if denied is not None:
            return denied

        serializer = InventoryOrderRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                drf_validation_error(serializer.errors),
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        data = serializer.validated_data

        try:
            response_body = unreserve_inventory(order_id=data["order_id"])
        except InventoryNotFound as exc:
            return not_found_error_response(exc)
        except InventoryConflict as exc:
            return conflict_error_response(exc)

        return Response(response_body, status=status.HTTP_200_OK)
