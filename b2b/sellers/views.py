from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import jwt
from django.conf import settings
from django.contrib.auth.hashers import check_password
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from catalog.api_errors import UNAUTHORIZED, error_body

from .auth import SellerJWTAuthentication
from .models import RevokedRefreshToken, Seller
from .serializers import (
    RefreshRequestSerializer,
    SellerCreateSerializer,
    SellerLoginSerializer,
    SellerResponseSerializer,
    SellerUpdateSerializer,
)


class SellerRegisterView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = SellerCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        seller = serializer.save()
        return Response(SellerResponseSerializer(seller).data, status=status.HTTP_201_CREATED)


def _build_seller_token(*, seller_id, token_type, lifetime_minutes):
    now = datetime.now(timezone.utc)
    payload = {
        "token_type": token_type,
        "seller_id": str(seller_id),
        "jti": str(uuid4()),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=lifetime_minutes)).timestamp()),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


class SellerLoginView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = SellerLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        username = serializer.validated_data["username"]
        password = serializer.validated_data["password"]
        try:
            seller = Seller.objects.get(email=username)
        except Seller.DoesNotExist:
            return Response(
                error_body(code=UNAUTHORIZED, message="Invalid credentials"),
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if not check_password(password, seller.password):
            return Response(
                error_body(code=UNAUTHORIZED, message="Invalid credentials"),
                status=status.HTTP_401_UNAUTHORIZED,
            )

        access_token = _build_seller_token(
            seller_id=seller.id, token_type="access", lifetime_minutes=60
        )
        refresh_token = _build_seller_token(
            seller_id=seller.id, token_type="refresh", lifetime_minutes=60 * 24 * 14
        )
        return Response(
            {
                "access_token": access_token,
                "refresh_token": refresh_token,
                "token_type": "bearer",
            },
            status=status.HTTP_200_OK,
        )


class SellerRefreshView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = RefreshRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        refresh_token = serializer.validated_data["refresh_token"]
        try:
            payload = jwt.decode(
                refresh_token, settings.SECRET_KEY, algorithms=["HS256"]
            )
        except jwt.PyJWTError:
            return Response(
                error_body(code=UNAUTHORIZED, message="Invalid refresh token"),
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if payload.get("token_type") != "refresh":
            return Response(
                error_body(code=UNAUTHORIZED, message="Invalid refresh token"),
                status=status.HTTP_401_UNAUTHORIZED,
            )

        seller_id = payload.get("seller_id")
        jti = payload.get("jti")
        if not seller_id or not jti:
            return Response(
                error_body(code=UNAUTHORIZED, message="Invalid refresh token"),
                status=status.HTTP_401_UNAUTHORIZED,
            )

        try:
            token_jti = UUID(str(jti))
        except ValueError:
            return Response(
                error_body(code=UNAUTHORIZED, message="Invalid refresh token"),
                status=status.HTTP_401_UNAUTHORIZED,
            )

        try:
            seller = Seller.objects.get(id=seller_id)
        except Seller.DoesNotExist:
            return Response(
                error_body(code=UNAUTHORIZED, message="Invalid refresh token"),
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if RevokedRefreshToken.objects.filter(jti=token_jti).exists():
            return Response(
                error_body(code=UNAUTHORIZED, message="Invalid refresh token"),
                status=status.HTTP_401_UNAUTHORIZED,
            )

        access_token = _build_seller_token(
            seller_id=seller.id, token_type="access", lifetime_minutes=60
        )
        new_refresh_token = _build_seller_token(
            seller_id=seller.id, token_type="refresh", lifetime_minutes=60 * 24 * 14
        )

        return Response(
            {
                "access_token": access_token,
                "refresh_token": new_refresh_token,
                "token_type": "bearer",
            },
            status=status.HTTP_200_OK,
        )


class SellerLogoutView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = RefreshRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        refresh_token = serializer.validated_data["refresh_token"]
        try:
            payload = jwt.decode(
                refresh_token, settings.SECRET_KEY, algorithms=["HS256"]
            )
        except jwt.PyJWTError:
            return Response(status=status.HTTP_204_NO_CONTENT)

        if payload.get("token_type") != "refresh":
            return Response(status=status.HTTP_204_NO_CONTENT)

        seller_id = payload.get("seller_id")
        jti = payload.get("jti")
        try:
            token_jti = UUID(str(jti))
        except (ValueError, TypeError):
            return Response(status=status.HTTP_204_NO_CONTENT)

        if seller_id:
            seller = Seller.objects.filter(id=seller_id).first()
            if seller:
                RevokedRefreshToken.objects.get_or_create(jti=token_jti, seller=seller)

        return Response(status=status.HTTP_204_NO_CONTENT)


class SellerProfileView(APIView):
    authentication_classes = [SellerJWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response(SellerResponseSerializer(request.user).data, status=status.HTTP_200_OK)


class SellerProfileUpdateView(APIView):
    authentication_classes = [SellerJWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request):
        serializer = SellerUpdateSerializer(
            request.user, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        seller = serializer.save()
        return Response(SellerResponseSerializer(seller).data, status=status.HTTP_200_OK)


class SellerProfileDeleteView(APIView):
    authentication_classes = [SellerJWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request):
        request.user.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
