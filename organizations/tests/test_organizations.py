"""API tests for organization create/list/retrieve/members."""

from __future__ import annotations

import pytest

from accounts.tests.factories import UserFactory
from organizations.models import Membership, Organization, Role
from organizations.tests.factories import MembershipFactory, OrganizationFactory

pytestmark = pytest.mark.django_db

ORGS = "/api/organizations"


def test_create_org_makes_caller_the_owner(as_user):
    user = UserFactory()
    client = as_user(user)
    resp = client.post(ORGS, {"name": "Acme Inc"})
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "Acme Inc"
    assert body["slug"] == "acme-inc"
    assert body["role"] == Role.OWNER

    membership = Membership.objects.get(organization_id=body["id"], user=user)
    assert membership.role == Role.OWNER
    assert Organization.objects.get(id=body["id"]).created_by == user


def test_create_org_requires_auth(api_client):
    assert api_client.post(ORGS, {"name": "Nope"}).status_code == 401


def test_org_endpoints_require_auth(api_client):
    org = OrganizationFactory()
    assert api_client.get(ORGS).status_code == 401
    assert api_client.get(f"{ORGS}/{org.id}").status_code == 401
    assert api_client.get(f"{ORGS}/{org.id}/members").status_code == 401


def test_create_org_rejects_blank_name(as_user):
    client = as_user(UserFactory())
    assert client.post(ORGS, {"name": "   "}).status_code == 400


def test_org_slugs_are_unique_for_duplicate_names(as_user):
    client = as_user(UserFactory())
    s1 = client.post(ORGS, {"name": "Same Name"}).json()["slug"]
    s2 = client.post(ORGS, {"name": "Same Name"}).json()["slug"]
    assert s1 == "same-name"
    assert s2 == "same-name-2"
    assert s1 != s2


def test_create_org_retries_on_slug_collision(as_user, monkeypatch):
    """Simulate a concurrent slug collision: first candidate is taken, retry wins."""
    from organizations import views

    OrganizationFactory(slug="taken")
    calls = {"n": 0}

    def fake_candidate(_name):
        calls["n"] += 1
        return "taken" if calls["n"] == 1 else "free-slug"

    monkeypatch.setattr(views, "_candidate_slug", fake_candidate)

    resp = as_user(UserFactory()).post(ORGS, {"name": "Whatever"})
    assert resp.status_code == 201
    assert resp.json()["slug"] == "free-slug"
    assert calls["n"] == 2  # collided once, then succeeded


def test_create_org_gives_up_after_persistent_collisions(as_user, monkeypatch):
    from organizations import views

    OrganizationFactory(slug="always-taken")
    monkeypatch.setattr(views, "_candidate_slug", lambda _name: "always-taken")

    resp = as_user(UserFactory()).post(ORGS, {"name": "Whatever"})
    assert resp.status_code == 500  # exhausted retries → APIException


def test_list_returns_only_callers_orgs_with_role(as_user):
    user = UserFactory()
    MembershipFactory(user=user, role=Role.OWNER)
    MembershipFactory(user=user, role=Role.MEMBER)
    OrganizationFactory()  # someone else's org

    resp = as_user(user).get(ORGS)
    assert resp.status_code == 200
    data = resp.json()["results"] if "results" in resp.json() else resp.json()
    assert len(data) == 2
    assert {row["role"] for row in data} == {Role.OWNER, Role.MEMBER}


def test_retrieve_member_ok_nonmember_404(as_user):
    member = MembershipFactory(role=Role.ADMIN)
    org = member.organization
    outsider = UserFactory()

    assert as_user(member.user).get(f"{ORGS}/{org.id}").status_code == 200
    # A non-member cannot even see that the org exists.
    assert as_user(outsider).get(f"{ORGS}/{org.id}").status_code == 404


def test_members_list_visible_to_members_only(as_user):
    org = OrganizationFactory()
    m1 = MembershipFactory(organization=org, role=Role.OWNER)
    MembershipFactory(organization=org, role=Role.MEMBER)
    outsider = UserFactory()

    resp = as_user(m1.user).get(f"{ORGS}/{org.id}/members")
    assert resp.status_code == 200
    rows = resp.json()["results"] if "results" in resp.json() else resp.json()
    assert len(rows) == 2
    assert all("email" in r["user"] for r in rows)

    assert as_user(outsider).get(f"{ORGS}/{org.id}/members").status_code == 404


def test_update_and_delete_are_not_allowed_yet(as_user):
    """PATCH/DELETE on orgs arrive in M4 (RBAC)."""
    member = MembershipFactory(role=Role.OWNER)
    client = as_user(member.user)
    assert client.patch(f"{ORGS}/{member.organization.id}", {"name": "X"}).status_code == 405
    assert client.delete(f"{ORGS}/{member.organization.id}").status_code == 405


def test_me_includes_organizations(as_user):
    user = UserFactory()
    client = as_user(user)
    client.post(ORGS, {"name": "My Org"})

    me = client.get("/api/auth/me").json()
    assert len(me["organizations"]) == 1
    assert me["organizations"][0]["role"] == Role.OWNER
    assert me["organizations"][0]["name"] == "My Org"
