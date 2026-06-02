"""Unit tests for the Stripe wrapper and the seed_plans command."""

from __future__ import annotations

import pytest
import stripe
from django.core.management import call_command

from billing import stripe_client
from billing.models import Plan
from billing.stripe_client import BillingNotConfigured
from organizations.models import Role
from organizations.tests.factories import MembershipFactory

pytestmark = pytest.mark.django_db


def test_ensure_customer_creates_and_caches(monkeypatch, settings):
    settings.STRIPE_SECRET_KEY = "sk_test_x"
    owner = MembershipFactory(role=Role.OWNER)
    sub = owner.organization.subscription
    monkeypatch.setattr(stripe.Customer, "create", classmethod(lambda cls, **kw: {"id": "cus_new"}))

    assert stripe_client.ensure_customer(sub, owner.organization) == "cus_new"
    sub.refresh_from_db()
    assert sub.stripe_customer_id == "cus_new"

    # Already has a customer → returns it without creating another.
    def _boom(cls, **kw):
        raise AssertionError("should not create a second customer")

    monkeypatch.setattr(stripe.Customer, "create", classmethod(_boom))
    assert stripe_client.ensure_customer(sub, owner.organization) == "cus_new"


def test_construct_event_requires_webhook_secret(settings):
    settings.STRIPE_WEBHOOK_SECRET = ""
    with pytest.raises(BillingNotConfigured):
        stripe_client.construct_event(b"{}", "sig")


def test_ensure_customer_requires_secret_key(settings):
    settings.STRIPE_SECRET_KEY = ""
    owner = MembershipFactory(role=Role.OWNER)
    with pytest.raises(BillingNotConfigured):
        stripe_client.ensure_customer(owner.organization.subscription, owner.organization)


def test_seed_plans_command_sets_prices_from_env(settings):
    settings.STRIPE_PRICE_PRO = "price_pro_env"
    settings.STRIPE_PRICE_BUSINESS = "price_biz_env"
    call_command("seed_plans")
    assert Plan.objects.get(code="pro").stripe_price_id == "price_pro_env"
    assert Plan.objects.get(code="business").stripe_price_id == "price_biz_env"
    assert Plan.objects.get(code="free").limits == {"max_projects": 3, "max_members": 3}
