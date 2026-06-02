"""Organization endpoints: org CRUD, member management, and invitations.

Tenancy: every endpoint is scoped to the caller's memberships via
``get_queryset`` (non-members get 404). RBAC: role gating follows the matrix in
``core.rbac`` exactly. Each org loaded via ``get_object`` carries the caller's
role in the annotation ``caller_role``.
"""

from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import OuterRef, Subquery
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.text import slugify
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import APIException, PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.rbac import MANAGER_ROLES, can_assign_role, can_manage_member, is_last_owner
from organizations.models import (
    Invitation,
    InvitationStatus,
    Membership,
    Organization,
    Role,
)
from organizations.serializers import (
    InvitationAcceptSerializer,
    InvitationCreateSerializer,
    InvitationSerializer,
    MemberRoleSerializer,
    MembershipSerializer,
    OrganizationSerializer,
)
from organizations.tasks import send_invitation_email_task


def _candidate_slug(name: str) -> str:
    base = slugify(name) or "org"
    slug = base
    suffix = 2
    while Organization.objects.filter(slug=slug).exists():
        slug = f"{base}-{suffix}"
        suffix += 1
    return slug


def _create_org_with_owner(user, name: str) -> Organization:
    """Create an org + the creator's Owner membership atomically, retrying on a
    slug race (recomputing against committed rows) to avoid a 500."""
    last_error: IntegrityError | None = None
    for _attempt in range(6):
        slug = _candidate_slug(name)
        try:
            with transaction.atomic():
                org = Organization.objects.create(name=name, slug=slug, created_by=user)
                Membership.objects.create(user=user, organization=org, role=Role.OWNER)
            return org
        except IntegrityError as exc:
            last_error = exc
    raise APIException(
        "Could not allocate a unique organization slug; please retry."
    ) from last_error


@extend_schema(tags=["organizations"])
class OrganizationViewSet(viewsets.ModelViewSet):
    serializer_class = OrganizationSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):
        user = self.request.user
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

    # --- org CRUD ---------------------------------------------------------- #
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        org = _create_org_with_owner(request.user, serializer.validated_data["name"])
        org.caller_role = Role.OWNER
        out = self.get_serializer(org)
        headers = self.get_success_headers(out.data)
        return Response(out.data, status=status.HTTP_201_CREATED, headers=headers)

    def update(self, request, *args, **kwargs):
        # Fetch once (not super().update(), which would re-fetch via get_object).
        org = self.get_object()
        if org.caller_role not in MANAGER_ROLES:  # owner/admin
            raise PermissionDenied("Only an owner or admin can update the organization.")
        serializer = self.get_serializer(
            org, data=request.data, partial=kwargs.get("partial", False)
        )
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(serializer.data)

    def destroy(self, request, *args, **kwargs):
        org = self.get_object()
        if org.caller_role != Role.OWNER:
            raise PermissionDenied("Only an owner can delete the organization.")
        self.perform_destroy(org)
        return Response(status=status.HTTP_204_NO_CONTENT)

    # --- members ----------------------------------------------------------- #
    @extend_schema(responses={200: MembershipSerializer(many=True)})
    @action(detail=True, methods=["get"])
    def members(self, request, pk=None):
        org = self.get_object()
        memberships = org.memberships.select_related("user").all()
        page = self.paginate_queryset(memberships)
        if page is not None:
            return self.get_paginated_response(MembershipSerializer(page, many=True).data)
        return Response(MembershipSerializer(memberships, many=True).data)

    @extend_schema(
        request=MemberRoleSerializer,
        responses={200: MembershipSerializer},
        parameters=[
            OpenApiParameter(
                "member_pk", location=OpenApiParameter.PATH, type=int, description="Membership id."
            )
        ],
    )
    @action(detail=True, methods=["patch", "delete"], url_path=r"members/(?P<member_pk>[^/.]+)")
    def member(self, request, pk=None, member_pk=None):
        org = self.get_object()
        actor_role = org.caller_role
        target = get_object_or_404(
            Membership.objects.select_related("user"), organization=org, pk=member_pk
        )

        if not can_manage_member(actor_role, target.role):
            raise PermissionDenied("You can't manage this member.")

        if request.method == "DELETE":
            if is_last_owner(target):
                raise ValidationError("Cannot remove the last owner of the organization.")
            target.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)

        # PATCH → change role
        payload = MemberRoleSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        new_role = payload.validated_data["role"]
        if not can_assign_role(actor_role, new_role):
            raise PermissionDenied("You can't assign a role higher than your own.")
        if target.role == Role.OWNER and new_role != Role.OWNER and is_last_owner(target):
            raise ValidationError("Cannot demote the last owner of the organization.")
        target.role = new_role
        target.save(update_fields=["role"])
        return Response(MembershipSerializer(target).data)

    # --- invitations ------------------------------------------------------- #
    @extend_schema(
        methods=["POST"], request=InvitationCreateSerializer, responses={201: InvitationSerializer}
    )
    @extend_schema(methods=["GET"], responses={200: InvitationSerializer(many=True)})
    @action(detail=True, methods=["get", "post"])
    def invitations(self, request, pk=None):
        org = self.get_object()
        actor_role = org.caller_role
        if actor_role not in MANAGER_ROLES:
            raise PermissionDenied("Only an owner or admin can manage invitations.")

        if request.method == "GET":
            qs = org.invitations.all()
            page = self.paginate_queryset(qs)
            if page is not None:
                return self.get_paginated_response(InvitationSerializer(page, many=True).data)
            return Response(InvitationSerializer(qs, many=True).data)

        # POST → create an invitation
        payload = InvitationCreateSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        email = payload.validated_data["email"]
        role = payload.validated_data["role"]

        if not can_assign_role(actor_role, role):
            raise PermissionDenied("You can't invite someone at a role higher than your own.")

        from billing import limits

        # Lock the org's billing row so the dedupe + member-cap check + create are
        # atomic (concurrent invites can't double-create or exceed max_members).
        with transaction.atomic():
            limits.lock_billing(org)
            if Membership.objects.filter(organization=org, user__email__iexact=email).exists():
                raise ValidationError("That user is already a member of this organization.")
            if org.invitations.filter(
                email__iexact=email, status=InvitationStatus.PENDING
            ).exists():
                raise ValidationError("An invitation is already pending for that email.")
            limits.check_can_invite_member(org)
            invitation = Invitation.objects.create(
                organization=org,
                email=email,
                role=role,
                invited_by=request.user,
                expires_at=timezone.now() + timedelta(days=settings.INVITATION_TIMEOUT_DAYS),
            )
        send_invitation_email_task.delay(invitation.id)
        return Response(InvitationSerializer(invitation).data, status=status.HTTP_201_CREATED)


@extend_schema(
    tags=["organizations"],
    request=InvitationAcceptSerializer,
    responses={200: MembershipSerializer},
)
class InvitationAcceptView(APIView):
    """Accept an invitation (authenticated). The token is for a specific email;
    the accepting user's email must match."""

    permission_classes = [IsAuthenticated]

    # One generic message for every "can't use this token" case (invalid, used,
    # or wrong account), so the response can't be used to enumerate who was
    # invited. Expiry is its own message (it leaks nothing about the invitee).
    _INVALID = "This invitation is invalid or has already been used."

    def post(self, request):
        payload = InvitationAcceptSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        token = payload.validated_data["token"]

        # Lock the invitation row so two concurrent accepts of the same token are
        # serialized: the first consumes it, the second sees ACCEPTED → clean 400
        # (no unique-constraint 500 race). The expired branch must persist its
        # status change, so it sets a flag and raises *after* the block commits
        # rather than raising inside it (which would roll the change back).
        membership = None
        expired = False
        with transaction.atomic():
            invitation = (
                Invitation.objects.select_for_update()
                .select_related("organization")
                .filter(token=token)
                .first()
            )
            if invitation is None or invitation.status != InvitationStatus.PENDING:
                raise ValidationError(self._INVALID)  # nothing written; rollback is a no-op
            if invitation.is_expired:
                invitation.status = InvitationStatus.EXPIRED
                invitation.save(update_fields=["status"])
                expired = True
            # Email mismatch returns the SAME 400 as an invalid token (uniform
            # response → no enumeration of pending invitees).
            elif request.user.email.lower() != invitation.email.lower():
                raise ValidationError(self._INVALID)
            else:
                membership, _created = Membership.objects.get_or_create(
                    user=request.user,
                    organization=invitation.organization,
                    defaults={"role": invitation.role},
                )
                invitation.status = InvitationStatus.ACCEPTED
                invitation.save(update_fields=["status"])

        if expired:
            raise ValidationError("This invitation has expired.")
        return Response(MembershipSerializer(membership).data, status=status.HTTP_200_OK)
