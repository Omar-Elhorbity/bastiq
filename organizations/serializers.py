"""Serializers for organizations and memberships."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from rest_framework import serializers

from organizations.models import Membership, Organization

User = get_user_model()


class MemberUserSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)

    class Meta:
        model = User
        fields = ["id", "email", "full_name"]
        read_only_fields = fields


class MembershipSerializer(serializers.ModelSerializer):
    user = MemberUserSerializer(read_only=True)

    class Meta:
        model = Membership
        fields = ["id", "user", "role", "created_at"]
        read_only_fields = fields


class OrganizationSerializer(serializers.ModelSerializer):
    # The requesting user's role in this organization.
    role = serializers.SerializerMethodField()

    class Meta:
        model = Organization
        fields = ["id", "name", "slug", "created_at", "role"]
        read_only_fields = ["id", "slug", "created_at", "role"]

    def validate_name(self, value: str) -> str:
        # Explicit (not relying on CharField's default trim) so the contract is
        # clear: whitespace-only names are rejected with a 400.
        value = value.strip()
        if not value:
            raise serializers.ValidationError("This field may not be blank.")
        return value

    def get_role(self, obj) -> str | None:
        # Prefer an annotation set by the viewset (avoids N+1 on list views).
        annotated = getattr(obj, "caller_role", None)
        if annotated is not None:
            return annotated
        request = self.context.get("request")
        if request is not None and request.user.is_authenticated:
            membership = obj.memberships.filter(user=request.user).first()
            return membership.role if membership else None
        return None
