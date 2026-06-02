"""Organization endpoints: create (→ Owner), list, retrieve, list members.

Member management (role changes, removal), update/delete, and invitations are
added in M4 (RBAC). Each organization endpoint is scoped to the caller's own
memberships via ``get_queryset`` — a non-member gets a 404, never another
tenant's data.
"""

from __future__ import annotations

from django.db import IntegrityError, transaction
from django.db.models import OuterRef, Subquery
from django.utils.text import slugify
from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import APIException
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from organizations.models import Membership, Organization, Role
from organizations.serializers import MembershipSerializer, OrganizationSerializer


def _candidate_slug(name: str) -> str:
    """Compute the next free slug from currently-committed rows."""
    base = slugify(name) or "org"
    slug = base
    suffix = 2
    while Organization.objects.filter(slug=slug).exists():
        slug = f"{base}-{suffix}"
        suffix += 1
    return slug


def _create_org_with_owner(user, name: str) -> Organization:
    """Create an org and the creator's Owner membership atomically.

    The slug is computed-then-inserted, so concurrent creates can collide on the
    unique slug constraint. We retry on IntegrityError — each retry recomputes
    the slug against now-committed rows — which closes the TOCTOU window without
    locking the whole table.
    """
    last_error: IntegrityError | None = None
    for _attempt in range(6):
        slug = _candidate_slug(name)
        try:
            with transaction.atomic():
                org = Organization.objects.create(name=name, slug=slug, created_by=user)
                Membership.objects.create(user=user, organization=org, role=Role.OWNER)
            return org
        except IntegrityError as exc:  # slug raced; recompute and retry
            last_error = exc
    raise APIException(
        "Could not allocate a unique organization slug; please retry."
    ) from last_error


@extend_schema(tags=["organizations"])
class OrganizationViewSet(viewsets.ModelViewSet):
    serializer_class = OrganizationSerializer
    permission_classes = [IsAuthenticated]
    # Update/delete are owner/admin actions added in M4.
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        user = self.request.user
        # Anonymous schema generation (drf-spectacular) hits this without a user.
        if not user or not user.is_authenticated:
            return Organization.objects.none()
        caller_role = Membership.objects.filter(organization=OuterRef("pk"), user=user).values(
            "role"
        )[:1]
        return (
            Organization.objects.filter(memberships__user=user)
            .annotate(caller_role=Subquery(caller_role))
            .distinct()
        )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        org = _create_org_with_owner(request.user, serializer.validated_data["name"])
        # Mirror the list annotation so the response doesn't issue an extra query.
        org.caller_role = Role.OWNER
        out = self.get_serializer(org)
        headers = self.get_success_headers(out.data)
        return Response(out.data, status=status.HTTP_201_CREATED, headers=headers)

    @extend_schema(responses={200: MembershipSerializer(many=True)})
    @action(detail=True, methods=["get"])
    def members(self, request, pk=None):
        # get_object() is scoped to the caller's orgs → 404 for non-members.
        org = self.get_object()
        memberships = org.memberships.select_related("user").all()
        page = self.paginate_queryset(memberships)
        if page is not None:
            serializer = MembershipSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        return Response(MembershipSerializer(memberships, many=True).data)
