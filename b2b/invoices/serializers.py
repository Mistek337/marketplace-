from rest_framework import serializers

from .models import Invoice, InvoiceItem


class InvoiceItemCreateSerializer(serializers.Serializer):
    sku_id = serializers.UUIDField()
    quantity = serializers.IntegerField(min_value=1)


class InvoiceCreateSerializer(serializers.Serializer):
    """OpenAPI InvoiceCreate."""

    items = InvoiceItemCreateSerializer(many=True)


class InvoiceItemResponseSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvoiceItem
        fields = ("id", "sku_id", "quantity", "accepted_quantity")


class InvoiceResponseSerializer(serializers.ModelSerializer):
    items = InvoiceItemResponseSerializer(many=True, read_only=True)

    class Meta:
        model = Invoice
        fields = (
            "id",
            "seller_id",
            "status",
            "items",
            "created_at",
            "updated_at",
            "accepted_at",
            "accepted_by",
        )
