"""Server-side plan-limit enforcement (projects + members)."""

from __future__ import annotations

import pytest

from billing.models import Plan
from organizations.models import Role
from organizations.tests.factories import MembershipFactory

pytestmark = pytest.mark.django_db

PROJECTS = "/api/projects"


def _invites_url(org_id):
    return f"/api/organizations/{org_id}/invitations"


def test_project_limit_enforced_then_raised_by_upgrade(as_user):
    owner = MembershipFactory(role=Role.OWNER)
    org = owner.organization  # Free plan → max_projects = 3
    client = as_user(owner.user, org=org)

    for i in range(3):
        assert client.post(PROJECTS, {"name": f"P{i}"}).status_code == 201
    # The 4th is blocked with a clear 402 (Payment Required).
    blocked = client.post(PROJECTS, {"name": "P4"})
    assert blocked.status_code == 402
    assert "upgrade" in str(blocked.json()).lower()

    # Upgrade to Pro (max_projects = 25) → the 4th now succeeds.
    org.subscription.plan = Plan.objects.get(code="pro")
    org.subscription.save(update_fields=["plan"])
    assert client.post(PROJECTS, {"name": "P4"}).status_code == 201


def test_business_plan_has_unlimited_projects(as_user):
    owner = MembershipFactory(role=Role.OWNER)
    org = owner.organization
    org.subscription.plan = Plan.objects.get(code="business")
    org.subscription.save(update_fields=["plan"])
    client = as_user(owner.user, org=org)
    for i in range(5):  # well past the Free cap
        assert client.post(PROJECTS, {"name": f"P{i}"}).status_code == 201


def test_member_invite_limit_enforced(as_user):
    owner = MembershipFactory(role=Role.OWNER)
    org = owner.organization  # Free → max_members = 3; owner already counts as 1
    client = as_user(owner.user)

    # members(1) + pending: two invites bring the total to 3.
    assert client.post(_invites_url(org.id), {"email": "a@x.com"}).status_code == 201
    assert client.post(_invites_url(org.id), {"email": "b@x.com"}).status_code == 201
    # The third would exceed max_members → 402.
    blocked = client.post(_invites_url(org.id), {"email": "c@x.com"})
    assert blocked.status_code == 402


def test_member_invite_limit_raised_by_upgrade(as_user):
    owner = MembershipFactory(role=Role.OWNER)
    org = owner.organization
    org.subscription.plan = Plan.objects.get(code="pro")  # max_members = 10
    org.subscription.save(update_fields=["plan"])
    client = as_user(owner.user)
    for i in range(5):
        assert client.post(_invites_url(org.id), {"email": f"m{i}@x.com"}).status_code == 201


def test_past_due_subscription_keeps_plan_limits(as_user):
    """Limits follow the plan, not the status — a PAST_DUE Pro org keeps Pro caps
    (they still owe; downgrade happens via the subscription.deleted webhook)."""
    from billing.models import SubscriptionStatus

    owner = MembershipFactory(role=Role.OWNER)
    org = owner.organization
    org.subscription.plan = Plan.objects.get(code="pro")
    org.subscription.status = SubscriptionStatus.PAST_DUE
    org.subscription.save(update_fields=["plan", "status"])
    client = as_user(owner.user, org=org)
    for i in range(5):  # past the Free cap of 3 — allowed because plan is Pro
        assert client.post(PROJECTS, {"name": f"P{i}"}).status_code == 201


def test_downgrade_keeps_existing_resources_but_blocks_new(as_user):
    """By design we never delete data on downgrade: an org over the new cap keeps
    its projects but can't create more until it's back under the limit."""
    from projects.tests.factories import ProjectFactory

    owner = MembershipFactory(role=Role.OWNER)
    org = owner.organization
    org.subscription.plan = Plan.objects.get(code="pro")
    org.subscription.save(update_fields=["plan"])
    for _ in range(5):  # 5 projects on Pro (over the Free cap of 3)
        ProjectFactory(organization=org)

    # Downgrade to Free (what the subscription.deleted webhook does).
    org.subscription.plan = Plan.objects.get(code="free")
    org.subscription.save(update_fields=["plan"])

    from projects.models import Project

    assert Project.objects.filter(organization=org).count() == 5  # data retained
    # But new creation is blocked until under the Free cap.
    assert as_user(owner.user, org=org).post(PROJECTS, {"name": "New"}).status_code == 402
