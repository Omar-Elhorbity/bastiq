"""Checkout & customer-portal endpoints (Stripe calls are mocked)."""

from __future__ import annotations

import pytest

from billing import stripe_client
from billing.models import Plan
from organizations.models import Role
from organizations.tests.factories import MembershipFactory

pytestmark = pytest.mark.django_db

CHECKOUT = "/api/billing/checkout"
PORTAL = "/api/billing/portal"


@pytest.fixture
def stripe_mock(monkeypatch):
    monkeypatch.setattr(stripe_client, "ensure_customer", lambda sub, org: "cus_test")
    monkeypatch.setattr(
        stripe_client,
        "create_checkout_session",
        lambda **kw: "https://checkout.stripe.test/session",
    )
    monkeypatch.setattr(
        stripe_client, "create_portal_session", lambda **kw: "https://portal.stripe.test/session"
    )


def test_owner_can_start_checkout(as_user, stripe_mock):
    Plan.objects.filter(code="pro").update(stripe_price_id="price_pro")
    owner = MembershipFactory(role=Role.OWNER)
    resp = as_user(owner.user, org=owner.organization).post(CHECKOUT, {"plan_code": "pro"})
    assert resp.status_code == 200
    assert resp.json()["checkout_url"] == "https://checkout.stripe.test/session"


def test_checkout_is_owner_only(as_user, stripe_mock):
    Plan.objects.filter(code="pro").update(stripe_price_id="price_pro")
    owner = MembershipFactory(role=Role.OWNER)
    org = owner.organization
    admin = MembershipFactory(organization=org, role=Role.ADMIN)
    member = MembershipFactory(organization=org, role=Role.MEMBER)
    assert as_user(admin.user, org=org).post(CHECKOUT, {"plan_code": "pro"}).status_code == 403
    assert as_user(member.user, org=org).post(CHECKOUT, {"plan_code": "pro"}).status_code == 403


def test_checkout_rejects_unknown_plan(as_user, stripe_mock):
    owner = MembershipFactory(role=Role.OWNER)
    resp = as_user(owner.user, org=owner.organization).post(CHECKOUT, {"plan_code": "enterprise"})
    assert resp.status_code == 400


def test_checkout_rejects_plan_without_price(as_user, stripe_mock):
    # 'pro' has no stripe_price_id configured here.
    owner = MembershipFactory(role=Role.OWNER)
    resp = as_user(owner.user, org=owner.organization).post(CHECKOUT, {"plan_code": "pro"})
    assert resp.status_code == 400


def test_owner_can_open_portal(as_user, stripe_mock):
    owner = MembershipFactory(role=Role.OWNER)
    org = owner.organization
    org.subscription.stripe_customer_id = "cus_existing"
    org.subscription.save(update_fields=["stripe_customer_id"])
    resp = as_user(owner.user, org=org).post(PORTAL)
    assert resp.status_code == 200
    assert resp.json()["portal_url"] == "https://portal.stripe.test/session"


def test_portal_requires_existing_customer(as_user, stripe_mock):
    owner = MembershipFactory(role=Role.OWNER)
    resp = as_user(owner.user, org=owner.organization).post(PORTAL)
    assert resp.status_code == 400


def test_checkout_returns_503_when_stripe_unconfigured(as_user, settings):
    # No stripe_mock → the real client checks STRIPE_SECRET_KEY.
    settings.STRIPE_SECRET_KEY = ""
    Plan.objects.filter(code="pro").update(stripe_price_id="price_pro")
    owner = MembershipFactory(role=Role.OWNER)
    resp = as_user(owner.user, org=owner.organization).post(CHECKOUT, {"plan_code": "pro"})
    assert resp.status_code == 503


def test_portal_returns_503_when_stripe_unconfigured(as_user, settings):
    settings.STRIPE_SECRET_KEY = ""
    owner = MembershipFactory(role=Role.OWNER)
    org = owner.organization
    org.subscription.stripe_customer_id = "cus_existing"
    org.subscription.save(update_fields=["stripe_customer_id"])
    resp = as_user(owner.user, org=org).post(PORTAL)
    assert resp.status_code == 503
