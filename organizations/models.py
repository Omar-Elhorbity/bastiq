"""Organizations (tenants) and their memberships.

An Organization is a tenant boundary; a Membership ties a user to an
organization with a role. The Owner/Admin/Member hierarchy is enforced in M4;
M2 establishes the models, org creation (creator → Owner), and the active-org
resolution used by tenant-scoped resources (M3+).
"""

from __future__ import annotations

from django.conf import settings
from django.db import models


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
    # NOTE: protection against removing/demoting the *last* Owner (so an org is
    # never left ownerless) is enforced in M4, where member management — the only
    # API path that demotes/removes members — is implemented ("can't demote last
    # owner"). M2 has no API to delete memberships.
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
