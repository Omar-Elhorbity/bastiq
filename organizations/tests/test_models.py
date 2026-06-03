"""Model-level tests for organizations."""

from __future__ import annotations

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from organizations.models import Membership, Organization, Role
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


# --- model-layer last-owner protection (defends the admin/shell too) --------- #
def test_clean_blocks_demoting_last_owner():
    owner = MembershipFactory(role=Role.OWNER)
    owner.role = Role.MEMBER
    with pytest.raises(ValidationError):
        owner.clean()


def test_clean_allows_demoting_owner_when_another_exists():
    owner1 = MembershipFactory(role=Role.OWNER)
    MembershipFactory(organization=owner1.organization, role=Role.OWNER)
    owner1.role = Role.MEMBER
    owner1.clean()  # no raise


def test_delete_blocks_removing_last_owner():
    owner = MembershipFactory(role=Role.OWNER)
    with pytest.raises(ValidationError):
        owner.delete()
    assert Membership.objects.filter(pk=owner.pk).exists()


def test_delete_non_owner_membership_works():
    owner = MembershipFactory(role=Role.OWNER)
    member = MembershipFactory(organization=owner.organization, role=Role.MEMBER)
    member.delete()
    assert not Membership.objects.filter(pk=member.pk).exists()


def test_org_cascade_delete_removes_sole_owner_membership():
    """Deleting the org cascades (collector bypasses Membership.delete()), so a
    single-owner org can still be deleted wholesale."""
    owner = MembershipFactory(role=Role.OWNER)
    org_id = owner.organization_id
    owner.organization.delete()
    assert not Organization.objects.filter(pk=org_id).exists()
    assert not Membership.objects.filter(organization_id=org_id).exists()
