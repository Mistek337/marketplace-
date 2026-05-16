from django.contrib.auth import get_user_model
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from cart.api_errors import error_body
from cart.services import merge_guest_into_user, parse_session_header

from .serializers import (
    RegisterRequestSerializer,
    LoginRequestSerializer,
    BuyerResponseSerializer,
    UpdateProfileRequestSerializer,
)
from .tokens import build_token_response


User = get_user_model()


class RegisterView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = RegisterRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                error_body(
                    code="VALIDATION_ERROR",
                    message="Invalid registration data",
                    details=serializer.errors,
                ),
                status=status.HTTP_400_BAD_REQUEST,
            )

        email = serializer.validated_data["email"]
        if User.objects.filter(email__iexact=email).exists():
            return Response(
                error_body(code="CONFLICT", message="Email already registered"),
                status=status.HTTP_409_CONFLICT,
            )

        user = serializer.save()
        return Response(build_token_response(user), status=status.HTTP_201_CREATED)


class LoginView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = LoginRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                error_body(
                    code="VALIDATION_ERROR",
                    message="Invalid login data",
                    details=serializer.errors,
                ),
                status=status.HTTP_400_BAD_REQUEST,
            )

        email = serializer.validated_data["email"]
        password = serializer.validated_data["password"]

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response(
                error_body(code="UNAUTHORIZED", message="Invalid credentials"),
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if not user.check_password(password):
            return Response(
                error_body(code="UNAUTHORIZED", message="Invalid credentials"),
                status=status.HTTP_401_UNAUTHORIZED,
            )

        guest_session_id = parse_session_header(request)
        if guest_session_id is not None:
            merge_guest_into_user(guest_session_id=guest_session_id, user=user)

        return Response(build_token_response(user), status=status.HTTP_200_OK)


class ProfileView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response(BuyerResponseSerializer(request.user).data)

    def patch(self, request):
        serializer = UpdateProfileRequestSerializer(
            request.user, data=request.data, partial=True
        )
        if not serializer.is_valid():
            return Response(
                error_body(
                    code="VALIDATION_ERROR",
                    message="Invalid profile data",
                    details=serializer.errors,
                ),
                status=status.HTTP_400_BAD_REQUEST,
            )
        user = serializer.save()
        return Response(BuyerResponseSerializer(user).data)
