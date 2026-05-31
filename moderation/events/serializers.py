from rest_framework import serializers


class IncomingB2BEventSerializer(serializers.Serializer):
    event_type = serializers.ChoiceField(
        choices=['PRODUCT_CREATED', 'PRODUCT_EDITED', 'PRODUCT_DELETED'],
    )
    idempotency_key = serializers.UUIDField()
    occurred_at = serializers.DateTimeField(required=False)
    payload = serializers.DictField()

    def validate(self, attrs):
        payload = attrs['payload']
        event_type = attrs['event_type']
        if 'product_id' not in payload:
            raise serializers.ValidationError({'payload': 'product_id is required'})
        if event_type in ('PRODUCT_CREATED', 'PRODUCT_EDITED') and 'seller_id' not in payload:
            raise serializers.ValidationError({'payload': 'seller_id is required'})
        if event_type == 'PRODUCT_EDITED' and 'json_after' not in payload:
            raise serializers.ValidationError({'payload': 'json_after is required'})
        if event_type == 'PRODUCT_CREATED' and 'json_after' not in payload:
            raise serializers.ValidationError({'payload': 'json_after is required'})
        return attrs
