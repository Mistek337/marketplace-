from datetime import timedelta

from rest_framework import serializers

from tickets.models import Ticket


class LoginRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField()


class RefreshRequestSerializer(serializers.Serializer):
    refresh_token = serializers.CharField()


class FieldReportSerializer(serializers.Serializer):
    field_path = serializers.CharField(max_length=512)
    message = serializers.CharField(max_length=1000)
    severity = serializers.ChoiceField(
        choices=['INFO', 'WARNING', 'ERROR'],
        default='ERROR',
        required=False,
    )


class ApproveRequestSerializer(serializers.Serializer):
    comment = serializers.CharField(max_length=2000, required=False, allow_blank=True)


class BlockDecisionRequestSerializer(serializers.Serializer):
    """OpenAPI BlockDecisionRequest."""

    blocking_reason_ids = serializers.ListField(
        child=serializers.UUIDField(),
        min_length=1,
    )
    comment = serializers.CharField(max_length=2000, required=False, allow_blank=True)
    field_reports = FieldReportSerializer(many=True, required=False, allow_empty=True)


class TicketResponseSerializer(serializers.ModelSerializer):
    assigned_moderator_id = serializers.UUIDField(read_only=True, allow_null=True)
    claim_expires_at = serializers.SerializerMethodField()

    class Meta:
        model = Ticket
        fields = [
            'id',
            'product_id',
            'seller_id',
            'category_id',
            'kind',
            'status',
            'queue_priority',
            'assigned_moderator_id',
            'claimed_at',
            'claim_expires_at',
            'decision_at',
            'created_at',
            'updated_at',
        ]

    def get_claim_expires_at(self, obj: Ticket):
        if not obj.claimed_at:
            return None
        expires = obj.claimed_at + timedelta(minutes=30)
        return expires.isoformat().replace('+00:00', 'Z')
