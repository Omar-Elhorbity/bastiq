"""Base viewset for tenant-scoped resources.

Subclasses set ``queryset`` and ``serializer_class`` for a model inheriting
``TenantScopedModel``. This base does the two things that keep tenants isolated,
in one audited place:

* ``get_queryset`` filters by ``request.organization`` — so no tenant queryset
  is ever evaluated without an organization filter (cross-org rows are simply
  not in the queryset → 404, never another tenant's data).
* ``perform_create`` stamps ``organization=request.organization`` — so the org
  is set server-side from the validated header, never from the request body.

``IsOrganizationMember`` (which resolves & validates ``request.organization``
from the ``X-Organization-ID`` header) is enforced here, so subclasses can't
forget it.
"""

from __future__ import annotations

from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from core.permissions import IsOrganizationMember


class TenantScopedViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, IsOrganizationMember]

    def get_queryset(self):
        queryset = super().get_queryset()
        org = getattr(self.request, "organization", None)
        if org is None:
            # No validated active org (e.g. schema generation) → expose nothing.
            return queryset.none()
        return queryset.filter(organization=org)

    def perform_create(self, serializer):
        serializer.save(organization=self.request.organization, **self.get_create_kwargs())

    def get_create_kwargs(self) -> dict:
        """Extra server-set fields on create (e.g. created_by). Override as needed."""
        return {}
