import jwt
from django.conf import settings
from rest_framework import authentication, exceptions

from .models import Seller


class SellerJWTAuthentication(authentication.BaseAuthentication):
    def authenticate(self, request):
        header = request.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            return None

        token = header.split(" ", 1)[1].strip()
        if not token:
            raise exceptions.AuthenticationFailed("Invalid token")

        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        except jwt.PyJWTError as exc:
            raise exceptions.AuthenticationFailed("Invalid token") from exc

        if payload.get("token_type") != "access":
            raise exceptions.AuthenticationFailed("Invalid token")

        seller_id = payload.get("seller_id")
        if not seller_id:
            raise exceptions.AuthenticationFailed("Invalid token")

        try:
            seller = Seller.objects.get(id=seller_id)
        except Seller.DoesNotExist as exc:
            raise exceptions.AuthenticationFailed("Invalid token") from exc

        return (seller, token)
