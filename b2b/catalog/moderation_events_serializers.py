"""Сериализаторы POST /api/v1/moderation/events (OpenAPI ModerationEventRequest)."""

from __future__ import annotations

from rest_framework import serializers


class FieldReportSerializer(serializers.Serializer):
    field_name = serializers.CharField()
    sku_id = serializers.UUIDField(required=False, allow_null=True)
    comment = serializers.CharField()


class ModerationEventRequestSerializer(serializers.Serializer):
    idempotency_key = serializers.UUIDField()
    product_id = serializers.UUIDField()
    event_type = serializers.ChoiceField(choices=["MODERATED", "BLOCKED"])
    moderator_id = serializers.UUIDField(required=False, allow_null=True)
    moderator_comment = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    blocking_reason_id = serializers.UUIDField(required=False, allow_null=True)
    hard_block = serializers.BooleanField(required=False, default=False)
    field_reports = FieldReportSerializer(many=True, required=False, allow_null=True)
    occurred_at = serializers.DateTimeField()

    def validate(self, attrs):
        event_type = attrs.get("event_type")
        if event_type == "BLOCKED" and not attrs.get("blocking_reason_id"):
            raise serializers.ValidationError(
                {"blocking_reason_id": "Required when event_type is BLOCKED."}
            )
        return attrs
