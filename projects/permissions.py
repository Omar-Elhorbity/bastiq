"""Object-level write permission for projects.

Read and create are open to any org member (member-level access is enforced by
``IsOrganizationMember``). Update and delete are restricted to org Owners/Admins
or the project's creator — the matrix in handoff §7.
"""

from __future__ import annotations

from rest_framework.permissions import SAFE_METHODS, BasePermission

from organizations.models import Role


class CanWriteProject(BasePermission):
    message = "Only an organization owner/admin or the project's creator can modify it."

    def has_object_permission(self, request, view, obj) -> bool:
        if request.method in SAFE_METHODS:
            return True
        membership = getattr(request, "membership", None)
        if membership is not None and membership.role in {Role.OWNER, Role.ADMIN}:
            return True
        return obj.created_by_id == request.user.id
