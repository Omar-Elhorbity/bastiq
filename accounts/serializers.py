"""Serializers for the auth flows."""

from __future__ import annotations

from django.conf import settings
from django.contrib.auth import get_user_model, password_validation
from django.core.exceptions import ValidationError as DjangoValidationError
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from accounts.tasks import (
    send_password_reset_email_task,
    send_verification_email_task,
)
from accounts.tokens import (
    TokenError,
    read_email_verification_token,
    read_password_reset_token,
)

User = get_user_model()


def _split_name(name: str) -> tuple[str, str]:
    name = (name or "").strip()
    if not name:
        return "", ""
    parts = name.split(None, 1)
    return parts[0], (parts[1] if len(parts) > 1 else "")


class UserOrganizationSerializer(serializers.Serializer):
    """A user's organization membership, as surfaced on /me."""

    id = serializers.IntegerField()
    name = serializers.CharField()
    slug = serializers.SlugField()
    role = serializers.CharField()


class UserSerializer(serializers.ModelSerializer):
    """Public representation of a user (used by /me and register response)."""

    full_name = serializers.CharField(read_only=True)
    organizations = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "first_name",
            "last_name",
            "full_name",
            "is_email_verified",
            "date_joined",
            "organizations",
        ]
        read_only_fields = fields

    @extend_schema_field(UserOrganizationSerializer(many=True))
    def get_organizations(self, obj):
        from organizations.models import Membership

        memberships = (
            Membership.objects.filter(user=obj)
            .select_related("organization")
            .order_by("organization__name")
        )
        return [
            {
                "id": m.organization_id,
                "name": m.organization.name,
                "slug": m.organization.slug,
                "role": m.role,
            }
            for m in memberships
        ]


class RegisterSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, style={"input_type": "password"})
    name = serializers.CharField(required=False, allow_blank=True, default="")

    def validate_email(self, value: str) -> str:
        value = value.strip().lower()
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value

    def validate(self, attrs):
        first, last = _split_name(attrs.get("name", ""))
        # Validate strength with user context (similarity to email/name).
        probe = User(email=attrs["email"], first_name=first, last_name=last)
        try:
            password_validation.validate_password(attrs["password"], user=probe)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"password": list(exc.messages)}) from exc
        return attrs

    def create(self, validated_data):
        first, last = _split_name(validated_data.get("name", ""))
        user = User.objects.create_user(
            email=validated_data["email"],
            password=validated_data["password"],
            first_name=first,
            last_name=last,
            is_email_verified=False,
        )
        # Async; in tests Celery runs eagerly and mail lands in mail.outbox.
        send_verification_email_task.delay(user.pk)
        return user


class VerifyEmailSerializer(serializers.Serializer):
    token = serializers.CharField(write_only=True)

    def validate(self, attrs):
        try:
            attrs["uid"] = read_email_verification_token(attrs["token"])
        except TokenError as exc:
            raise serializers.ValidationError({"token": str(exc)}) from exc
        return attrs

    def save(self) -> None:
        # Idempotent: verifying an already-verified account is a no-op success.
        User.objects.filter(pk=self.validated_data["uid"]).update(is_email_verified=True)


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def save(self) -> None:
        email = self.validated_data["email"].strip().lower()
        # Enumeration-safe: never reveal whether the account exists. Only active
        # users get an email; the response is identical either way.
        user = User.objects.filter(email__iexact=email, is_active=True).first()
        if user is not None:
            send_password_reset_email_task.delay(user.pk)


class PasswordResetConfirmSerializer(serializers.Serializer):
    token = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, style={"input_type": "password"})

    def validate(self, attrs):
        try:
            user = read_password_reset_token(attrs["token"])
        except TokenError as exc:
            raise serializers.ValidationError({"token": str(exc)}) from exc
        try:
            password_validation.validate_password(attrs["new_password"], user=user)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"new_password": list(exc.messages)}) from exc
        attrs["user"] = user
        return attrs

    def save(self):
        from accounts.sessions import revoke_all_refresh_tokens

        user = self.validated_data["user"]
        user.set_password(self.validated_data["new_password"])
        # Changing the password rotates the reset-token fingerprint → single-use.
        user.save(update_fields=["password"])
        # Kill existing sessions: a compromised refresh token can't be reused.
        revoke_all_refresh_tokens(user)
        return user


class LoginSerializer(TokenObtainPairSerializer):
    """JWT obtain serializer with extra claims and optional verification gate."""

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["email"] = user.email
        token["is_email_verified"] = user.is_email_verified
        return token

    def validate(self, attrs):
        data = super().validate(attrs)  # authenticates; sets self.user
        if settings.LOGIN_REQUIRE_VERIFIED_EMAIL and not self.user.is_email_verified:
            raise serializers.ValidationError(
                "Email address is not verified.", code="email_not_verified"
            )
        return data
