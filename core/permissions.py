"""Tenancy permissions — the isolation perimeter lives here, and ONLY here.

``IsOrganizationMember`` is the single, audited place where the active
organization is resolved. It reads the ``X-Organization-ID`` request header,
validates it against the authenticated user's ``Membership``, and attaches the
result to the request as ``request.organization`` and ``request.membership``.

The invariant (see handoff §6a): the active org is derived from the
authenticated user's membership — **never** from the request body or query
params — so a user physically cannot act on an org they don't belong to and
cannot smuggle another org's id through a payload.
"""

from __future__ import annotations

from rest_framework.permissions import BasePermission

ORG_ID_HEADER = "X-Organization-ID"


class IsOrganizationMember(BasePermission):
    """Authenticated + a member of the org named in ``X-Organization-ID``.

    On success, sets ``request.organization`` and ``request.membership``.
    """

    message = f"Provide a valid {ORG_ID_HEADER} header for an organization you belong to."

    def has_permission(self, request, view) -> bool:
        user = getattr(request, "user", None)
        if user is None or not user.is_authenticated:
            return False

        raw = request.headers.get(ORG_ID_HEADER)
        if not raw:
            return False

        # The header must be an integer pk; anything else is simply "no access"
        # (avoids leaking a DB error and avoids type-coercion surprises).
        # Note: every denial path returns the same generic message — we never
        # reveal whether an org exists or whether the user is/ isn't a member.
        try:
            org_id = int(raw)
        except (TypeError, ValueError):
            return False

        # Import here to keep the import graph clean (core depends on the
        # organizations domain only at call time).
        from organizations.models import Membership

        membership = (
            Membership.objects.select_related("organization")
            .filter(user=user, organization_id=org_id)
            .first()
        )
        if membership is None:
            return False

        request.organization = membership.organization
        request.membership = membership
        return True
