"""Plans listing, the auto-created Free subscription, and the subscription view."""

from __future__ import annotations

import pytest

from accounts.tests.factories import UserFactory
from billing.models import Plan, Subscription, SubscriptionStatus
from organizations.models import Role
from organizations.tests.factories import MembershipFactory, OrganizationFactory

pytestmark = pytest.mark.django_db

PLANS = "/api/billing/plans"
SUBSCRIPTION = "/api/billing/subscription"


def test_default_plans_are_seeded():
    assert set(Plan.objects.values_list("code", flat=True)) >= {"free", "pro", "business"}
    free = Plan.objects.get(code="free")
    assert free.limits == {"max_projects": 3, "max_members": 3}
    assert Plan.objects.get(code="business").limits == {"max_projects": None, "max_members": None}


def test_new_org_gets_a_free_subscription():
    org = OrganizationFactory()
    sub = Subscription.objects.get(organization=org)
    assert sub.plan.code == "free"
    assert sub.status == SubscriptionStatus.ACTIVE


def test_plans_endpoint_lists_active_plans(as_user):
    Plan.objects.filter(code="business").update(is_active=False)
    resp = as_user(UserFactory()).get(PLANS)
    assert resp.status_code == 200
    codes = {p["code"] for p in resp.json()}
    assert "free" in codes and "pro" in codes
    assert "business" not in codes


def test_plans_requires_auth(api_client):
    assert api_client.get(PLANS).status_code == 401


def test_subscription_endpoint_returns_current_plan(as_user):
    owner = MembershipFactory(role=Role.OWNER)
    resp = as_user(owner.user, org=owner.organization).get(SUBSCRIPTION)
    assert resp.status_code == 200
    assert resp.json()["plan"]["code"] == "free"
    assert resp.json()["status"] == SubscriptionStatus.ACTIVE


def test_subscription_visible_to_any_member(as_user):
    owner = MembershipFactory(role=Role.OWNER)
    member = MembershipFactory(organization=owner.organization, role=Role.MEMBER)
    assert as_user(member.user, org=owner.organization).get(SUBSCRIPTION).status_code == 200


def test_subscription_requires_membership_header(as_user):
    owner = MembershipFactory(role=Role.OWNER)
    # No X-Organization-ID header.
    assert as_user(owner.user).get(SUBSCRIPTION).status_code == 403
    # Non-member with a foreign org header.
    other = OrganizationFactory()
    assert as_user(owner.user, org=other).get(SUBSCRIPTION).status_code == 403
