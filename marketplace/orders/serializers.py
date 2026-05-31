from rest_framework import serializers


class OrderItemSnapshotSerializer(serializers.Serializer):
    sku_id = serializers.UUIDField()
    quantity = serializers.IntegerField(min_value=1)
    unit_price = serializers.IntegerField(min_value=0)


class OrderCreateRequestSerializer(serializers.Serializer):
    address_id = serializers.UUIDField()
    payment_method_id = serializers.UUIDField()
    comment = serializers.CharField(max_length=1000, required=False, allow_blank=True, default="")
    items_snapshot = OrderItemSnapshotSerializer(many=True, required=False)


class OrderCancelRequestSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=500, required=False, allow_blank=True, default="")
