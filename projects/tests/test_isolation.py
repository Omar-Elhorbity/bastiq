"""THE critical milestone test: multi-tenant isolation for Projects.

Proves org B cannot read or write org A's projects, that the active org comes
only from the validated header (never the body), and that switching the active
org switches what's visible.
"""

from __future__ import annotations

import pytest

from organizations.models import Role
from organizations.tests.factories import MembershipFactory, OrganizationFactory
from projects.models import Project
from projects.tests.factories import ProjectFactory

pytestmark = pytest.mark.django_db

PROJECTS = "/api/projects"


def test_org_b_cannot_read_org_a_project(as_user):
    """The headline guarantee: customer B can't see customer A's data."""
    a = MembershipFactory(role=Role.OWNER)
    b = MembershipFactory(role=Role.OWNER)
    a_project = ProjectFactory(organization=a.organization, created_by=a.user)

    b_client = as_user(b.user, org=b.organization)
    # Direct fetch of A's project under B's context → 404 (not 403 — B must not
    # learn the object exists).
    assert b_client.get(f"{PROJECTS}/{a_project.id}").status_code == 404
    # And it never appears in B's list.
    listing = b_client.get(PROJECTS).json()
    rows = listing["results"] if "results" in listing else listing
    assert rows == []

    # Sanity: A *can* see its own project.
    a_client = as_user(a.user, org=a.organization)
    assert a_client.get(f"{PROJECTS}/{a_project.id}").status_code == 200


def test_org_b_cannot_write_org_a_project(as_user):
    a = MembershipFactory(role=Role.OWNER)
    b = MembershipFactory(role=Role.OWNER)
    a_project = ProjectFactory(organization=a.organization, created_by=a.user)
    b_client = as_user(b.user, org=b.organization)

    assert b_client.patch(f"{PROJECTS}/{a_project.id}", {"name": "hijacked"}).status_code == 404
    assert b_client.delete(f"{PROJECTS}/{a_project.id}").status_code == 404
    a_project.refresh_from_db()
    assert a_project.name != "hijacked"


def test_organization_is_never_taken_from_request_body(as_user):
    """Even if the body names another org, the project lands in the active org."""
    a = MembershipFactory(role=Role.OWNER)
    other = OrganizationFactory()
    a_client = as_user(a.user, org=a.organization)

    resp = a_client.post(
        PROJECTS,
        {"name": "Smuggle", "organization": other.id, "created_by": 99999},
        format="json",
    )
    assert resp.status_code == 201
    project = Project.objects.get(id=resp.json()["id"])
    # Org came from the header (a.organization), not the body's `other`.
    assert project.organization_id == a.organization_id
    # created_by came from the authenticated user, not the body.
    assert project.created_by_id == a.user_id


def test_organization_cannot_be_changed_via_patch(as_user):
    """PATCH naming another org changes nothing but the editable fields."""
    a = MembershipFactory(role=Role.OWNER)
    other = OrganizationFactory()
    a_project = ProjectFactory(organization=a.organization, created_by=a.user)
    client = as_user(a.user, org=a.organization)

    resp = client.patch(
        f"{PROJECTS}/{a_project.id}",
        {"name": "Renamed", "organization": other.id, "created_by": 99999},
        format="json",
    )
    assert resp.status_code == 200
    a_project.refresh_from_db()
    assert a_project.organization_id == a.organization_id  # unchanged
    assert a_project.created_by_id == a.user_id  # unchanged
    assert a_project.name == "Renamed"


def test_query_param_organization_is_ignored(as_user):
    """A ?organization=<other> query param cannot widen the active-org scope."""
    member = MembershipFactory(role=Role.OWNER)
    other = OrganizationFactory()
    ProjectFactory(organization=member.organization, name="Mine")
    ProjectFactory(organization=other, name="Theirs")

    client = as_user(member.user, org=member.organization)
    resp = client.get(f"{PROJECTS}?organization={other.id}")
    assert resp.status_code == 200
    rows = resp.json()
    rows = rows["results"] if "results" in rows else rows
    assert {r["name"] for r in rows} == {"Mine"}


def test_create_scopes_to_active_org(as_user):
    member = MembershipFactory(role=Role.OWNER)
    client = as_user(member.user, org=member.organization)
    resp = client.post(PROJECTS, {"name": "Roadmap"})
    assert resp.status_code == 201
    project = Project.objects.get(id=resp.json()["id"])
    assert project.organization_id == member.organization_id
    assert project.created_by_id == member.user_id


def test_list_returns_only_active_org_projects(as_user):
    """A user in two orgs sees only the active org's projects (demo step 6)."""
    user_membership_a = MembershipFactory(role=Role.OWNER)
    user = user_membership_a.user
    org_a = user_membership_a.organization
    org_b = OrganizationFactory()
    MembershipFactory(user=user, organization=org_b, role=Role.OWNER)

    ProjectFactory(organization=org_a, name="A1")
    ProjectFactory(organization=org_a, name="A2")
    ProjectFactory(organization=org_b, name="B1")

    client_a = as_user(user, org=org_a)
    rows_a = client_a.get(PROJECTS).json()
    rows_a = rows_a["results"] if "results" in rows_a else rows_a
    assert {r["name"] for r in rows_a} == {"A1", "A2"}

    client_b = as_user(user, org=org_b)
    rows_b = client_b.get(PROJECTS).json()
    rows_b = rows_b["results"] if "results" in rows_b else rows_b
    assert {r["name"] for r in rows_b} == {"B1"}


def test_requires_active_org_header(as_user):
    member = MembershipFactory(role=Role.OWNER)
    no_header = as_user(member.user)  # no X-Organization-ID
    assert no_header.get(PROJECTS).status_code == 403
    assert no_header.post(PROJECTS, {"name": "x"}).status_code == 403


def test_non_member_org_header_denied(as_user):
    member = MembershipFactory(role=Role.OWNER)
    other = OrganizationFactory()  # member is NOT in `other`
    client = as_user(member.user, org=other)
    assert client.get(PROJECTS).status_code == 403


def test_unauthenticated_denied(api_client):
    project = ProjectFactory()
    api_client.credentials(HTTP_X_ORGANIZATION_ID=str(project.organization_id))
    assert api_client.get(PROJECTS).status_code in (401, 403)
