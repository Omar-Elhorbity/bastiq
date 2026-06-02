"""Invitation invite + accept flow."""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.utils import timezone

from accounts.tests.factories import UserFactory
from organizations.models import Invitation, InvitationStatus, Membership, Role
from organizations.tests.factories import MembershipFactory

pytestmark = pytest.mark.django_db

ORG = "/api/organizations"
ACCEPT = "/api/invitations/accept"


def _invites_url(org_id):
    return f"{ORG}/{org_id}/invitations"


# --- creating invitations ---------------------------------------------------- #
def test_owner_can_invite_and_email_is_sent(as_user, mailoutbox):
    owner = MembershipFactory(role=Role.OWNER)
    resp = as_user(owner.user).post(
        _invites_url(owner.organization.id), {"email": "New@Person.com", "role": "member"}
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["email"] == "new@person.com"  # normalised
    assert body["status"] == InvitationStatus.PENDING
    assert len(mailoutbox) == 1
    assert mailoutbox[0].to == ["new@person.com"]


def test_admin_can_invite_member_but_not_owner(as_user):
    owner = MembershipFactory(role=Role.OWNER)
    org = owner.organization
    admin = MembershipFactory(organization=org, role=Role.ADMIN)
    client = as_user(admin.user)

    assert (
        client.post(_invites_url(org.id), {"email": "m@x.com", "role": "member"}).status_code == 201
    )
    # Admin cannot invite at a higher rank than their own.
    assert (
        client.post(_invites_url(org.id), {"email": "o@x.com", "role": "owner"}).status_code == 403
    )


def test_admin_can_invite_at_admin_rank(as_user):
    owner = MembershipFactory(role=Role.OWNER)
    org = owner.organization
    admin = MembershipFactory(organization=org, role=Role.ADMIN)
    resp = as_user(admin.user).post(_invites_url(org.id), {"email": "peer@x.com", "role": "admin"})
    assert resp.status_code == 201
    assert resp.json()["role"] == Role.ADMIN


def test_owner_can_invite_at_any_rank(as_user):
    owner = MembershipFactory(role=Role.OWNER)
    org = owner.organization
    client = as_user(owner.user)
    assert (
        client.post(_invites_url(org.id), {"email": "a@x.com", "role": "admin"}).status_code == 201
    )
    assert (
        client.post(_invites_url(org.id), {"email": "o@x.com", "role": "owner"}).status_code == 201
    )


def test_member_cannot_invite(as_user):
    owner = MembershipFactory(role=Role.OWNER)
    org = owner.organization
    member = MembershipFactory(organization=org, role=Role.MEMBER)
    assert as_user(member.user).post(_invites_url(org.id), {"email": "x@x.com"}).status_code == 403


def test_cannot_invite_existing_member(as_user):
    owner = MembershipFactory(role=Role.OWNER)
    org = owner.organization
    existing = MembershipFactory(organization=org, role=Role.MEMBER)
    resp = as_user(owner.user).post(_invites_url(org.id), {"email": existing.user.email})
    assert resp.status_code == 400


def test_cannot_double_invite_pending(as_user):
    owner = MembershipFactory(role=Role.OWNER)
    org = owner.organization
    client = as_user(owner.user)
    assert client.post(_invites_url(org.id), {"email": "dup@x.com"}).status_code == 201
    assert client.post(_invites_url(org.id), {"email": "dup@x.com"}).status_code == 400


def test_owner_can_list_invitations(as_user):
    owner = MembershipFactory(role=Role.OWNER)
    org = owner.organization
    client = as_user(owner.user)
    client.post(_invites_url(org.id), {"email": "a@x.com"})
    client.post(_invites_url(org.id), {"email": "b@x.com"})

    resp = client.get(_invites_url(org.id))
    assert resp.status_code == 200
    rows = resp.json()
    rows = rows["results"] if "results" in rows else rows
    assert {r["email"] for r in rows} == {"a@x.com", "b@x.com"}


def test_member_cannot_list_invitations(as_user):
    owner = MembershipFactory(role=Role.OWNER)
    org = owner.organization
    member = MembershipFactory(organization=org, role=Role.MEMBER)
    assert as_user(member.user).get(_invites_url(org.id)).status_code == 403


def test_non_member_cannot_invite_404(as_user):
    owner = MembershipFactory(role=Role.OWNER)
    outsider = UserFactory()
    assert (
        as_user(outsider)
        .post(_invites_url(owner.organization.id), {"email": "x@x.com"})
        .status_code
        == 404
    )


# --- accepting invitations --------------------------------------------------- #
def _make_invite(org, email, role=Role.MEMBER, inviter=None):
    return Invitation.objects.create(
        organization=org,
        email=email,
        role=role,
        invited_by=inviter,
        expires_at=timezone.now() + timedelta(days=7),
    )


def test_accept_creates_membership_with_invited_role(as_user):
    owner = MembershipFactory(role=Role.OWNER)
    org = owner.organization
    invitee = UserFactory(email="invitee@x.com")
    invite = _make_invite(org, "invitee@x.com", role=Role.ADMIN, inviter=owner.user)

    resp = as_user(invitee).post(ACCEPT, {"token": invite.token})
    assert resp.status_code == 200
    assert resp.json()["role"] == Role.ADMIN
    assert Membership.objects.filter(user=invitee, organization=org, role=Role.ADMIN).exists()
    invite.refresh_from_db()
    assert invite.status == InvitationStatus.ACCEPTED


def test_accept_requires_matching_email(as_user):
    owner = MembershipFactory(role=Role.OWNER)
    invite = _make_invite(owner.organization, "intended@x.com")
    wrong_user = UserFactory(email="someone-else@x.com")
    resp = as_user(wrong_user).post(ACCEPT, {"token": invite.token})
    # Uniform 400 (same as an invalid token) so the endpoint can't be used to
    # enumerate who has a pending invitation.
    assert resp.status_code == 400
    assert not Membership.objects.filter(user=wrong_user).exists()


def test_accept_rejects_expired(as_user):
    owner = MembershipFactory(role=Role.OWNER)
    invitee = UserFactory(email="late@x.com")
    invite = Invitation.objects.create(
        organization=owner.organization,
        email="late@x.com",
        role=Role.MEMBER,
        expires_at=timezone.now() - timedelta(seconds=1),
    )
    resp = as_user(invitee).post(ACCEPT, {"token": invite.token})
    assert resp.status_code == 400
    invite.refresh_from_db()
    assert invite.status == InvitationStatus.EXPIRED


def test_accept_is_single_use(as_user):
    owner = MembershipFactory(role=Role.OWNER)
    invitee = UserFactory(email="once@x.com")
    invite = _make_invite(owner.organization, "once@x.com")

    assert as_user(invitee).post(ACCEPT, {"token": invite.token}).status_code == 200
    # Re-using the (now accepted) token fails.
    assert as_user(invitee).post(ACCEPT, {"token": invite.token}).status_code == 400


def test_accept_rejects_garbage_token(as_user):
    user = UserFactory()
    assert as_user(user).post(ACCEPT, {"token": "nope"}).status_code == 400


def test_accept_requires_auth(api_client):
    owner = MembershipFactory(role=Role.OWNER)
    invite = _make_invite(owner.organization, "x@x.com")
    assert api_client.post(ACCEPT, {"token": invite.token}).status_code == 401
