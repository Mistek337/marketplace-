from rest_framework import serializers

from tickets.models import Ticket


class TicketResponseSerializer(serializers.ModelSerializer):
    assigned_moderator_id = serializers.UUIDField(read_only=True, allow_null=True)

    class Meta:
        model = Ticket
        fields = [
            'id',
            'product_id',
            'seller_id',
            'kind',
            'status',
            'queue_priority',
            'assigned_moderator_id',
            'claimed_at',
            'decision_at',
            'created_at',
            'updated_at',
        ]


class ApproveRequestSerializer(serializers.Serializer):
    comment = serializers.CharField(max_length=2000, required=False, allow_blank=True)
