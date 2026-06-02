"""Server-side plan-limit enforcement (handoff §6c).

Limits are checked at creation time and never trust the client. A limit of None
means unlimited. ``PlanLimitExceeded`` is a 402 (Payment Required) so clients get
a clear, actionable "upgrade your plan" signal.
"""

from __future__ import annotations

from rest_framework.exceptions import APIException

from billing.models import DEFAULT_PLANS, FREE_PLAN_CODE, Subscription


class PlanLimitExceeded(APIException):
    status_code = 402  # Payment Required
    default_detail = "Your plan's limit has been reached. Upgrade to add more."
    default_code = "plan_limit_reached"


def lock_billing(organization) -> None:
    """Serialize limit-guarded creates for an org by locking its subscription row.

    Must be called inside ``transaction.atomic()``; the lock is held until the
    surrounding transaction commits, so two concurrent creates can't both pass a
    count check and exceed the cap (closes the TOCTOU window).
    """
    list(Subscription.objects.select_for_update().filter(organization=organization))


def _limit(organization, key: str) -> int | None:
    """The org's cap for ``key`` (None = unlimited). Falls back to the Free
    plan's defaults if the org somehow has no subscription/plan."""
    subscription = getattr(organization, "subscription", None)
    if subscription is not None and subscription.plan_id is not None:
        return subscription.plan.limit(key)
    return DEFAULT_PLANS[FREE_PLAN_CODE]["limits"].get(key)


def check_can_create_project(organization) -> None:
    from projects.models import Project

    limit = _limit(organization, "max_projects")
    if limit is not None and Project.objects.filter(organization=organization).count() >= limit:
        raise PlanLimitExceeded(
            f"Your plan allows at most {limit} projects. Upgrade to create more."
        )


def check_can_invite_member(organization) -> None:
    """Counts current members plus still-pending invitations, so an org can't
    over-allocate seats by stacking pending invites."""
    from organizations.models import InvitationStatus

    limit = _limit(organization, "max_members")
    if limit is None:
        return
    members = organization.memberships.count()
    pending = organization.invitations.filter(status=InvitationStatus.PENDING).count()
    if members + pending >= limit:
        raise PlanLimitExceeded(f"Your plan allows at most {limit} members. Upgrade to add more.")
