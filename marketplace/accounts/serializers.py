from django.contrib.auth import get_user_model
from rest_framework import serializers


User = get_user_model()


class RegisterRequestSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ("email", "password", "first_name", "last_name", "phone")

    def create(self, validated_data):
        password = validated_data.pop("password")
        user = User.objects.create_user(password=password, **validated_data)
        return user


class LoginRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField()


class BuyerResponseSerializer(serializers.ModelSerializer):
    date_of_birth = serializers.SerializerMethodField()
    updated_at = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "id",
            "email",
            "first_name",
            "last_name",
            "phone",
            "date_of_birth",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields

    def get_date_of_birth(self, obj):
        return None

    def get_updated_at(self, obj):
        return None


class UserResponseSerializer(BuyerResponseSerializer):
    """Обратная совместимость."""

    class Meta(BuyerResponseSerializer.Meta):
        fields = BuyerResponseSerializer.Meta.fields + ("role",)


class UpdateProfileRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("first_name", "last_name", "phone")
        extra_kwargs = {field: {"required": False} for field in fields}

