from django.contrib.auth.hashers import make_password
from rest_framework import serializers

from .models import Seller


class SellerCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Seller
        fields = (
            "email",
            "password",
            "first_name",
            "last_name",
            "middle_name",
            "company_name",
            "phone",
        )
        extra_kwargs = {
            "password": {"write_only": True},
            "middle_name": {"required": False, "allow_null": True, "allow_blank": True},
            "phone": {"required": False, "allow_null": True, "allow_blank": True},
        }

    def create(self, validated_data):
        validated_data["password"] = make_password(validated_data["password"])
        return super().create(validated_data)


class SellerResponseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Seller
        fields = (
            "id",
            "email",
            "first_name",
            "last_name",
            "middle_name",
            "company_name",
            "phone",
            "created_at",
            "updated_at",
        )


class SellerLoginSerializer(serializers.Serializer):
    grant_type = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    username = serializers.EmailField()
    password = serializers.CharField()
    scope = serializers.CharField(required=False, allow_blank=True, default="")
    client_id = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    client_secret = serializers.CharField(
        required=False, allow_null=True, allow_blank=True
    )


class RefreshRequestSerializer(serializers.Serializer):
    refresh_token = serializers.CharField()


class SellerUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Seller
        fields = (
            "first_name",
            "last_name",
            "middle_name",
            "company_name",
            "phone",
        )
        extra_kwargs = {
            "first_name": {"required": False},
            "last_name": {"required": False},
            "middle_name": {"required": False, "allow_null": True, "allow_blank": True},
            "company_name": {"required": False},
            "phone": {"required": False, "allow_null": True, "allow_blank": True},
        }
