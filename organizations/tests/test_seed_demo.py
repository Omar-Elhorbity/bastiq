"""The seed_demo command builds the documented walkthrough data, idempotently."""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command

from billing.models import Subscription
from organizations.models import Membership, Organization, Role
from projects.models import Project

pytestmark = pytest.mark.django_db

User = get_user_model()


def test_seed_demo_creates_org_users_and_projects():
    call_command("seed_demo")

    org = Organization.objects.get(slug="acme-inc")
    assert Subscription.objects.get(organization=org).plan.code == "free"
    assert Project.objects.filter(organization=org).count() == 2

    roles = {m.user.email: m.role for m in Membership.objects.filter(organization=org)}
    assert roles == {
        "owner@acme.test": Role.OWNER,
        "admin@acme.test": Role.ADMIN,
        "member@acme.test": Role.MEMBER,
    }

    owner = User.objects.get(email="owner@acme.test")
    assert owner.is_email_verified
    assert owner.check_password("BastiqDemo!23")


def test_seed_demo_is_idempotent():
    call_command("seed_demo")
    call_command("seed_demo")  # second run must not duplicate
    org = Organization.objects.get(slug="acme-inc")
    assert Organization.objects.filter(slug="acme-inc").count() == 1
    assert Membership.objects.filter(organization=org).count() == 3
    assert Project.objects.filter(organization=org).count() == 2
