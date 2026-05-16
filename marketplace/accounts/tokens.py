from django.conf import settings
from rest_framework_simplejwt.tokens import RefreshToken


def build_token_response(user) -> dict:
    refresh = RefreshToken.for_user(user)
    access = refresh.access_token
    lifetime = settings.SIMPLE_JWT["ACCESS_TOKEN_LIFETIME"]
    return {
        "access_token": str(access),
        "refresh_token": str(refresh),
        "token_type": "Bearer",
        "expires_in": int(lifetime.total_seconds()),
        "user_id": str(user.id),
    }
