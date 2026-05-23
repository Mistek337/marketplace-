"""Сериализаторы OpenAPI Inventory (reserve / unreserve)."""

from rest_framework import serializers


class InventoryItemSerializer(serializers.Serializer):
    sku_id = serializers.UUIDField()
    quantity = serializers.IntegerField(min_value=1)


class ReserveRequestSerializer(serializers.Serializer):
    idempotency_key = serializers.UUIDField()
    order_id = serializers.UUIDField()
    items = InventoryItemSerializer(many=True, allow_empty=False)


class InventoryOrderRequestSerializer(serializers.Serializer):
    order_id = serializers.UUIDField()
    items = InventoryItemSerializer(many=True, allow_empty=False)
