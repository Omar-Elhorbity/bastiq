"""Organizations (tenants) and their memberships.

An Organization is a tenant boundary; a Membership ties a user to an
organization with a role. The Owner/Admin/Member hierarchy is enforced in M4;
M2 establishes the models, org creation (creator → Owner), and the active-org
resolution used by tenant-scoped resources (M3+).
"""

from __future__ import annotations

import secrets

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class Role(models.TextChoices):
    OWNER = "owner", "Owner"
    ADMIN = "admin", "Admin"
    MEMBER = "member", "Member"

    @classmethod
    def rank(cls, value: str) -> int:
        """Privilege rank (higher = more powerful). Used by RBAC checks in M4."""
        return {cls.MEMBER: 1, cls.ADMIN: 2, cls.OWNER: 3}.get(value, 0)


class Organization(models.Model):
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Membership(models.Model):
    # An org must never be left ownerless. The API enforces this (core.rbac), and
    # clean()/delete() below enforce it at the MODEL layer too — so the admin,
    # inline forms, and shell can't orphan an org either. Org cascade-delete still
    # works: the delete collector bypasses Model.delete().
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="memberships"
    )
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="memberships"
    )
    role = models.CharField(max_length=16, choices=Role.choices, default=Role.MEMBER)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["organization_id", "user_id"]
        constraints = [
            models.UniqueConstraint(fields=["user", "organization"], name="uniq_user_org"),
        ]

    def __str__(self) -> str:
        return f"{self.user_id} @ {self.organization_id} ({self.role})"

    @property
    def is_owner(self) -> bool:
        return self.role == Role.OWNER

    @property
    def is_admin_or_owner(self) -> bool:
        return self.role in {Role.OWNER, Role.ADMIN}

    def _org_owner_count(self) -> int:
        return Membership.objects.filter(
            organization_id=self.organization_id, role=Role.OWNER
        ).count()

    def clean(self) -> None:
        # Block demoting the last owner (runs via full_clean in admin/forms).
        if self.pk:
            current_role = (
                Membership.objects.filter(pk=self.pk).values_list("role", flat=True).first()
            )
            if (
                current_role == Role.OWNER
                and self.role != Role.OWNER
                and self._org_owner_count() <= 1
            ):
                raise ValidationError("Cannot demote the last owner of the organization.")

    def delete(self, *args, **kwargs):
        # Block removing the last owner. Cascade deletes (e.g. deleting the org)
        # go through the collector, which bypasses this, so they still work.
        if self.role == Role.OWNER and self._org_owner_count() <= 1:
            raise ValidationError("Cannot remove the last owner of the organization.")
        return super().delete(*args, **kwargs)


def generate_invitation_token() -> str:
    """Opaque, unguessable token stored on the Invitation row."""
    return secrets.token_urlsafe(32)


class InvitationStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    ACCEPTED = "accepted", "Accepted"
    REVOKED = "revoked", "Revoked"
    EXPIRED = "expired", "Expired"


class Invitation(models.Model):
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="invitations"
    )
    email = models.EmailField()
    role = models.CharField(max_length=16, choices=Role.choices, default=Role.MEMBER)
    token = models.CharField(
        max_length=255, unique=True, default=generate_invitation_token, editable=False
    )
    status = models.CharField(
        max_length=16, choices=InvitationStatus.choices, default=InvitationStatus.PENDING
    )
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["organization", "status"])]

    def __str__(self) -> str:
        return f"{self.email} → {self.organization_id} ({self.role}, {self.status})"

    @property
    def is_expired(self) -> bool:
        return timezone.now() >= self.expires_at
