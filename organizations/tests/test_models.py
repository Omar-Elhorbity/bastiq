"""Model-level tests for organizations."""

from __future__ import annotations

import pytest
from django.db import IntegrityError

from organizations.models import Membership, Role
from organizations.tests.factories import MembershipFactory, OrganizationFactory

pytestmark = pytest.mark.django_db


def test_role_rank_ordering():
    assert Role.rank(Role.OWNER) > Role.rank(Role.ADMIN) > Role.rank(Role.MEMBER)
    assert Role.rank("bogus") == 0


def test_membership_uniqueness_per_user_org():
    membership = MembershipFactory()
    with pytest.raises(IntegrityError):
        Membership.objects.create(
            user=membership.user, organization=membership.organization, role=Role.ADMIN
        )


def test_membership_role_helpers():
    owner = MembershipFactory(role=Role.OWNER)
    admin = MembershipFactory(role=Role.ADMIN)
    member = MembershipFactory(role=Role.MEMBER)
    assert owner.is_owner and owner.is_admin_or_owner
    assert not admin.is_owner and admin.is_admin_or_owner
    assert not member.is_owner and not member.is_admin_or_owner


def test_same_user_can_belong_to_multiple_orgs():
    org_a = OrganizationFactory()
    org_b = OrganizationFactory()
    m = MembershipFactory(organization=org_a, role=Role.OWNER)
    Membership.objects.create(user=m.user, organization=org_b, role=Role.MEMBER)
    assert Membership.objects.filter(user=m.user).count() == 2
