"""Project CRUD within the active org (role gating is M4; plan limits are M5)."""

from __future__ import annotations

import pytest

from organizations.models import Role
from organizations.tests.factories import MembershipFactory
from projects.models import Project
from projects.tests.factories import ProjectFactory

pytestmark = pytest.mark.django_db

PROJECTS = "/api/projects"


def test_member_can_create_and_read(as_user):
    member = MembershipFactory(role=Role.MEMBER)
    client = as_user(member.user, org=member.organization)

    created = client.post(PROJECTS, {"name": "Launch", "description": "Q3 launch"})
    assert created.status_code == 201
    pid = created.json()["id"]

    fetched = client.get(f"{PROJECTS}/{pid}")
    assert fetched.status_code == 200
    assert fetched.json()["name"] == "Launch"
    assert fetched.json()["description"] == "Q3 launch"


def test_member_can_update_and_delete_within_org(as_user):
    # In M3 any member may modify projects in their org; M4 narrows this.
    member = MembershipFactory(role=Role.MEMBER)
    project = ProjectFactory(organization=member.organization, created_by=member.user)
    client = as_user(member.user, org=member.organization)

    patched = client.patch(f"{PROJECTS}/{project.id}", {"name": "Renamed"})
    assert patched.status_code == 200
    assert patched.json()["name"] == "Renamed"

    assert client.delete(f"{PROJECTS}/{project.id}").status_code == 204
    assert not Project.objects.filter(id=project.id).exists()


def test_create_requires_name(as_user):
    member = MembershipFactory(role=Role.OWNER)
    client = as_user(member.user, org=member.organization)
    assert client.post(PROJECTS, {"description": "no name"}).status_code == 400


def test_response_never_exposes_organization_field(as_user):
    member = MembershipFactory(role=Role.OWNER)
    client = as_user(member.user, org=member.organization)
    body = client.post(PROJECTS, {"name": "X"}).json()
    # organization is an internal, server-set field — not part of the contract.
    assert "organization" not in body
    assert set(body) == {"id", "name", "description", "created_by", "created_at"}


def test_description_length_is_bounded(as_user):
    member = MembershipFactory(role=Role.OWNER)
    client = as_user(member.user, org=member.organization)
    resp = client.post(PROJECTS, {"name": "Big", "description": "x" * 5001})
    assert resp.status_code == 400
    assert "description" in resp.json()


def test_tenant_manager_for_org():
    a = ProjectFactory()
    ProjectFactory()  # different org
    qs = Project.objects.for_org(a.organization)
    assert list(qs) == [a]
