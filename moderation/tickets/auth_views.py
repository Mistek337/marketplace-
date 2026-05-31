from uuid import UUID

import jwt
from django.conf import settings
from django.contrib.auth.hashers import check_password
from django.utils import timezone as django_tz
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from events.api_errors import UNAUTHORIZED, error_body
from tickets.auth_tokens import ACCESS_TOKEN_MINUTES, build_access_token, build_refresh_token
from tickets.models import Moderator, RevokedRefreshToken
from tickets.serializers import LoginRequestSerializer, RefreshRequestSerializer


class LoginAPIView(APIView):
    """POST /api/v1/auth/login — OpenAPI Auth tag."""

    authentication_classes = []
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = LoginRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data['email']
        password = serializer.validated_data['password']
        try:
            moderator = Moderator.objects.get(email=email, is_active=True)
        except Moderator.DoesNotExist:
            return Response(
                error_body(code=UNAUTHORIZED, message='Invalid credentials'),
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if not check_password(password, moderator.password):
            return Response(
                error_body(code=UNAUTHORIZED, message='Invalid credentials'),
                status=status.HTTP_401_UNAUTHORIZED,
            )

        Moderator.objects.filter(pk=moderator.pk).update(last_login_at=django_tz.now())

        return Response(
            {
                'access_token': build_access_token(moderator_id=moderator.id, role=moderator.role),
                'refresh_token': build_refresh_token(moderator_id=moderator.id, role=moderator.role),
                'token_type': 'Bearer',
                'expires_in': ACCESS_TOKEN_MINUTES * 60,
                'user_id': str(moderator.id),
                'role': moderator.role,
            },
            status=status.HTTP_200_OK,
        )


class RefreshAPIView(APIView):
    """POST /api/v1/auth/refresh."""

    authentication_classes = []
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = RefreshRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        refresh_token = serializer.validated_data['refresh_token']
        try:
            payload = jwt.decode(refresh_token, settings.SECRET_KEY, algorithms=['HS256'])
        except jwt.PyJWTError:
            return Response(
                error_body(code=UNAUTHORIZED, message='Invalid refresh token'),
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if payload.get('token_type') != 'refresh':
            return Response(
                error_body(code=UNAUTHORIZED, message='Invalid refresh token'),
                status=status.HTTP_401_UNAUTHORIZED,
            )

        user_id = payload.get('user_id')
        jti = payload.get('jti')
        role = payload.get('role', Moderator.Role.MODERATOR)
        if not user_id or not jti:
            return Response(
                error_body(code=UNAUTHORIZED, message='Invalid refresh token'),
                status=status.HTTP_401_UNAUTHORIZED,
            )

        try:
            token_jti = UUID(str(jti))
        except ValueError:
            return Response(
                error_body(code=UNAUTHORIZED, message='Invalid refresh token'),
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if RevokedRefreshToken.objects.filter(jti=token_jti).exists():
            return Response(
                error_body(code=UNAUTHORIZED, message='Invalid refresh token'),
                status=status.HTTP_401_UNAUTHORIZED,
            )

        try:
            moderator = Moderator.objects.get(id=user_id, is_active=True)
        except Moderator.DoesNotExist:
            return Response(
                error_body(code=UNAUTHORIZED, message='Invalid refresh token'),
                status=status.HTTP_401_UNAUTHORIZED,
            )

        return Response(
            {
                'access_token': build_access_token(moderator_id=moderator.id, role=moderator.role),
                'refresh_token': build_refresh_token(moderator_id=moderator.id, role=moderator.role),
                'token_type': 'Bearer',
                'expires_in': ACCESS_TOKEN_MINUTES * 60,
                'user_id': str(moderator.id),
                'role': moderator.role,
            },
            status=status.HTTP_200_OK,
        )


class LogoutAPIView(APIView):
    """POST /api/v1/auth/logout — 204."""

    def post(self, request):
        return Response(status=status.HTTP_204_NO_CONTENT)
