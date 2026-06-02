"""Billing permission: owner-only actions (checkout, portal).

Builds on ``IsOrganizationMember`` (which sets ``request.membership`` from the
active-org header), then requires the Owner role.
"""

from __future__ import annotations

from rest_framework.permissions import BasePermission

from organizations.models import Role


class IsOrganizationOwner(BasePermission):
    message = "Only the organization owner can manage billing."

    def has_permission(self, request, view) -> bool:
        membership = getattr(request, "membership", None)
        return membership is not None and membership.role == Role.OWNER
