"""The permission matrix, encoded as API tests (handoff §6b)."""

from __future__ import annotations

import pytest

from organizations.models import Membership, Organization, Role
from organizations.tests.factories import MembershipFactory

pytestmark = pytest.mark.django_db

ORG = "/api/organizations"


# --- org update / delete ---------------------------------------------------- #
def test_owner_and_admin_can_update_org_member_cannot(as_user):
    owner = MembershipFactory(role=Role.OWNER)
    org = owner.organization
    admin = MembershipFactory(organization=org, role=Role.ADMIN)
    member = MembershipFactory(organization=org, role=Role.MEMBER)

    assert as_user(owner.user).patch(f"{ORG}/{org.id}", {"name": "By Owner"}).status_code == 200
    assert as_user(admin.user).patch(f"{ORG}/{org.id}", {"name": "By Admin"}).status_code == 200
    assert as_user(member.user).patch(f"{ORG}/{org.id}", {"name": "By Member"}).status_code == 403


def test_only_owner_can_delete_org(as_user):
    owner = MembershipFactory(role=Role.OWNER)
    org = owner.organization
    admin = MembershipFactory(organization=org, role=Role.ADMIN)

    assert as_user(admin.user).delete(f"{ORG}/{org.id}").status_code == 403
    assert as_user(owner.user).delete(f"{ORG}/{org.id}").status_code == 204
    assert not Organization.objects.filter(id=org.id).exists()


def test_non_member_cannot_update_org_404(as_user):
    owner = MembershipFactory(role=Role.OWNER)
    outsider = MembershipFactory(role=Role.OWNER)  # owner of a *different* org
    assert (
        as_user(outsider.user).patch(f"{ORG}/{owner.organization.id}", {"name": "x"}).status_code
        == 404
    )


# --- changing member roles --------------------------------------------------- #
def test_owner_can_promote_member_to_admin(as_user):
    owner = MembershipFactory(role=Role.OWNER)
    org = owner.organization
    member = MembershipFactory(organization=org, role=Role.MEMBER)

    resp = as_user(owner.user).patch(f"{ORG}/{org.id}/members/{member.id}", {"role": "admin"})
    assert resp.status_code == 200
    member.refresh_from_db()
    assert member.role == Role.ADMIN


def test_admin_cannot_grant_owner(as_user):
    owner = MembershipFactory(role=Role.OWNER)
    org = owner.organization
    admin = MembershipFactory(organization=org, role=Role.ADMIN)
    member = MembershipFactory(organization=org, role=Role.MEMBER)

    resp = as_user(admin.user).patch(f"{ORG}/{org.id}/members/{member.id}", {"role": "owner"})
    assert resp.status_code == 403
    member.refresh_from_db()
    assert member.role == Role.MEMBER


def test_admin_cannot_modify_an_owner(as_user):
    owner = MembershipFactory(role=Role.OWNER)
    org = owner.organization
    admin = MembershipFactory(organization=org, role=Role.ADMIN)

    resp = as_user(admin.user).patch(f"{ORG}/{org.id}/members/{owner.id}", {"role": "member"})
    assert resp.status_code == 403
    owner.refresh_from_db()
    assert owner.role == Role.OWNER


def test_member_cannot_change_roles(as_user):
    owner = MembershipFactory(role=Role.OWNER)
    org = owner.organization
    member = MembershipFactory(organization=org, role=Role.MEMBER)
    other = MembershipFactory(organization=org, role=Role.MEMBER)

    resp = as_user(member.user).patch(f"{ORG}/{org.id}/members/{other.id}", {"role": "admin"})
    assert resp.status_code == 403


def test_cannot_demote_last_owner(as_user):
    owner = MembershipFactory(role=Role.OWNER)
    org = owner.organization
    resp = as_user(owner.user).patch(f"{ORG}/{org.id}/members/{owner.id}", {"role": "member"})
    assert resp.status_code == 400
    owner.refresh_from_db()
    assert owner.role == Role.OWNER


def test_can_demote_owner_when_another_owner_exists(as_user):
    owner1 = MembershipFactory(role=Role.OWNER)
    org = owner1.organization
    owner2 = MembershipFactory(organization=org, role=Role.OWNER)
    resp = as_user(owner1.user).patch(f"{ORG}/{org.id}/members/{owner2.id}", {"role": "member"})
    assert resp.status_code == 200
    owner2.refresh_from_db()
    assert owner2.role == Role.MEMBER


def test_owner_can_demote_admin_to_member(as_user):
    owner = MembershipFactory(role=Role.OWNER)
    org = owner.organization
    admin = MembershipFactory(organization=org, role=Role.ADMIN)
    resp = as_user(owner.user).patch(f"{ORG}/{org.id}/members/{admin.id}", {"role": "member"})
    assert resp.status_code == 200
    admin.refresh_from_db()
    assert admin.role == Role.MEMBER


def test_admin_can_manage_a_peer_admin(as_user):
    """An admin may manage memberships at or below their own rank (not Owner)."""
    owner = MembershipFactory(role=Role.OWNER)
    org = owner.organization
    actor = MembershipFactory(organization=org, role=Role.ADMIN)
    peer = MembershipFactory(organization=org, role=Role.ADMIN)
    resp = as_user(actor.user).patch(f"{ORG}/{org.id}/members/{peer.id}", {"role": "member"})
    assert resp.status_code == 200
    peer.refresh_from_db()
    assert peer.role == Role.MEMBER


def test_admin_can_promote_member_to_admin(as_user):
    owner = MembershipFactory(role=Role.OWNER)
    org = owner.organization
    actor = MembershipFactory(organization=org, role=Role.ADMIN)
    member = MembershipFactory(organization=org, role=Role.MEMBER)
    resp = as_user(actor.user).patch(f"{ORG}/{org.id}/members/{member.id}", {"role": "admin"})
    assert resp.status_code == 200
    member.refresh_from_db()
    assert member.role == Role.ADMIN


# --- removing members -------------------------------------------------------- #
def test_owner_can_remove_member(as_user):
    owner = MembershipFactory(role=Role.OWNER)
    org = owner.organization
    member = MembershipFactory(organization=org, role=Role.MEMBER)
    assert as_user(owner.user).delete(f"{ORG}/{org.id}/members/{member.id}").status_code == 204
    assert not Membership.objects.filter(id=member.id).exists()


def test_admin_can_remove_member_and_peer_admin(as_user):
    owner = MembershipFactory(role=Role.OWNER)
    org = owner.organization
    admin = MembershipFactory(organization=org, role=Role.ADMIN)
    member = MembershipFactory(organization=org, role=Role.MEMBER)
    peer_admin = MembershipFactory(organization=org, role=Role.ADMIN)
    client = as_user(admin.user)
    assert client.delete(f"{ORG}/{org.id}/members/{member.id}").status_code == 204
    assert client.delete(f"{ORG}/{org.id}/members/{peer_admin.id}").status_code == 204


def test_owner_can_remove_admin(as_user):
    owner = MembershipFactory(role=Role.OWNER)
    org = owner.organization
    admin = MembershipFactory(organization=org, role=Role.ADMIN)
    assert as_user(owner.user).delete(f"{ORG}/{org.id}/members/{admin.id}").status_code == 204
    assert not Membership.objects.filter(id=admin.id).exists()


def test_admin_cannot_remove_owner(as_user):
    owner = MembershipFactory(role=Role.OWNER)
    org = owner.organization
    admin = MembershipFactory(organization=org, role=Role.ADMIN)
    assert as_user(admin.user).delete(f"{ORG}/{org.id}/members/{owner.id}").status_code == 403
    assert Membership.objects.filter(id=owner.id).exists()


def test_member_cannot_remove_anyone(as_user):
    owner = MembershipFactory(role=Role.OWNER)
    org = owner.organization
    member = MembershipFactory(organization=org, role=Role.MEMBER)
    other = MembershipFactory(organization=org, role=Role.MEMBER)
    client = as_user(member.user)
    assert client.delete(f"{ORG}/{org.id}/members/{other.id}").status_code == 403
    assert client.delete(f"{ORG}/{org.id}/members/{member.id}").status_code == 403


def test_cannot_remove_last_owner(as_user):
    owner = MembershipFactory(role=Role.OWNER)
    org = owner.organization
    assert as_user(owner.user).delete(f"{ORG}/{org.id}/members/{owner.id}").status_code == 400


def test_member_management_on_foreign_member_404(as_user):
    owner = MembershipFactory(role=Role.OWNER)
    org = owner.organization
    foreign = MembershipFactory(role=Role.MEMBER)  # belongs to another org
    resp = as_user(owner.user).delete(f"{ORG}/{org.id}/members/{foreign.id}")
    assert resp.status_code == 404
