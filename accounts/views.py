"""Auth views: register, verify, login/refresh, password reset, /me."""

from __future__ import annotations

from drf_spectacular.utils import OpenApiResponse, extend_schema, inline_serializer
from rest_framework import generics, serializers, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenRefreshView

from accounts.serializers import (
    LoginSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    RegisterSerializer,
    UserSerializer,
    VerifyEmailSerializer,
)

_DetailResponse = inline_serializer(
    name="DetailResponse", fields={"detail": serializers.CharField()}
)


@extend_schema(tags=["auth"])
class RegisterView(generics.CreateAPIView):
    """Register a new (unverified) user and send a verification email."""

    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]
    throttle_scope = "register"

    @extend_schema(responses={201: UserSerializer})
    def create(self, request: Request, *args, **kwargs) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)


@extend_schema(
    tags=["auth"],
    request=VerifyEmailSerializer,
    responses={200: OpenApiResponse(_DetailResponse, "Email verified.")},
)
class VerifyEmailView(APIView):
    """Confirm an email address from a signed verification token."""

    permission_classes = [AllowAny]
    throttle_scope = "email_verify"

    def post(self, request: Request) -> Response:
        serializer = VerifyEmailSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"detail": "Email address verified."}, status=status.HTTP_200_OK)


@extend_schema(tags=["auth"])
class LoginView(generics.GenericAPIView):
    """Obtain a JWT access/refresh pair from email + password."""

    serializer_class = LoginSerializer
    permission_classes = [AllowAny]
    throttle_scope = "login"

    def post(self, request: Request) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.validated_data, status=status.HTTP_200_OK)


@extend_schema(tags=["auth"])
class RefreshView(TokenRefreshView):
    """Exchange a refresh token for a new access token."""

    throttle_scope = "login"


@extend_schema(
    tags=["auth"],
    request=PasswordResetRequestSerializer,
    responses={202: OpenApiResponse(_DetailResponse, "Reset email sent if the account exists.")},
)
class PasswordResetRequestView(APIView):
    """Request a password-reset email (always returns 202; no user enumeration)."""

    permission_classes = [AllowAny]
    throttle_scope = "password_reset"

    def post(self, request: Request) -> Response:
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            {"detail": "If an account with that email exists, a reset link has been sent."},
            status=status.HTTP_202_ACCEPTED,
        )


@extend_schema(
    tags=["auth"],
    request=PasswordResetConfirmSerializer,
    responses={200: OpenApiResponse(_DetailResponse, "Password updated.")},
)
class PasswordResetConfirmView(APIView):
    """Set a new password from a signed (single-use) reset token."""

    permission_classes = [AllowAny]
    throttle_scope = "password_reset"

    def post(self, request: Request) -> Response:
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"detail": "Password has been reset."}, status=status.HTTP_200_OK)


@extend_schema(tags=["auth"])
class MeView(generics.RetrieveAPIView):
    """Return the authenticated user. (Memberships/orgs are added in M2.)"""

    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user
