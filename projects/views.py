"""Project endpoints — CRUD scoped to the active organization.

All isolation behaviour comes from ``TenantScopedViewSet``: the queryset is
filtered to ``request.organization`` and ``organization`` is stamped on create.
Role-based gating of update/delete (owner/admin or creator) is added in M4; the
plan-limit check on create is added in M5.
"""

from __future__ import annotations

from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.permissions import IsAuthenticated

from core.permissions import ORG_ID_HEADER, IsOrganizationMember
from core.viewsets import TenantScopedViewSet
from projects.models import Project
from projects.permissions import CanWriteProject
from projects.serializers import ProjectSerializer

_ORG_HEADER_PARAM = OpenApiParameter(
    name=ORG_ID_HEADER,
    location=OpenApiParameter.HEADER,
    required=True,
    type=int,
    description="Active organization id. Must be an org you're a member of.",
)


@extend_schema(tags=["projects"], parameters=[_ORG_HEADER_PARAM])
class ProjectViewSet(TenantScopedViewSet):
    serializer_class = ProjectSerializer
    queryset = Project.objects.all()
    # IsOrganizationMember scopes to the active org; CanWriteProject gates
    # update/delete to owner/admin or the creator.
    permission_classes = [IsAuthenticated, IsOrganizationMember, CanWriteProject]

    def get_create_kwargs(self) -> dict:
        return {"created_by": self.request.user}
