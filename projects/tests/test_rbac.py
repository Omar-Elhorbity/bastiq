"""Project write authorization: owner/admin or the creator (handoff §7)."""

from __future__ import annotations

import pytest

from organizations.models import Role
from organizations.tests.factories import MembershipFactory
from projects.models import Project
from projects.tests.factories import ProjectFactory

pytestmark = pytest.mark.django_db

PROJECTS = "/api/projects"


@pytest.fixture
def org_with_team():
    owner = MembershipFactory(role=Role.OWNER)
    org = owner.organization
    admin = MembershipFactory(organization=org, role=Role.ADMIN)
    creator = MembershipFactory(organization=org, role=Role.MEMBER)
    other = MembershipFactory(organization=org, role=Role.MEMBER)
    project = ProjectFactory(organization=org, created_by=creator.user)
    return {
        "org": org,
        "owner": owner,
        "admin": admin,
        "creator": creator,
        "other": other,
        "project": project,
    }


def test_creator_can_update_and_delete(as_user, org_with_team):
    t = org_with_team
    client = as_user(t["creator"].user, org=t["org"])
    assert client.patch(f"{PROJECTS}/{t['project'].id}", {"name": "by creator"}).status_code == 200
    assert client.delete(f"{PROJECTS}/{t['project'].id}").status_code == 204


def test_admin_can_update_and_delete_any_project(as_user, org_with_team):
    t = org_with_team
    client = as_user(t["admin"].user, org=t["org"])
    assert client.patch(f"{PROJECTS}/{t['project'].id}", {"name": "by admin"}).status_code == 200
    assert client.delete(f"{PROJECTS}/{t['project'].id}").status_code == 204


def test_owner_can_update_and_delete_any_project(as_user, org_with_team):
    t = org_with_team
    client = as_user(t["owner"].user, org=t["org"])
    assert client.patch(f"{PROJECTS}/{t['project'].id}", {"name": "by owner"}).status_code == 200
    assert client.delete(f"{PROJECTS}/{t['project'].id}").status_code == 204
    assert not Project.objects.filter(id=t["project"].id).exists()


def test_non_creator_member_cannot_update_or_delete(as_user, org_with_team):
    t = org_with_team
    client = as_user(t["other"].user, org=t["org"])
    assert client.patch(f"{PROJECTS}/{t['project'].id}", {"name": "nope"}).status_code == 403
    assert client.delete(f"{PROJECTS}/{t['project'].id}").status_code == 403


def test_any_member_can_still_read(as_user, org_with_team):
    t = org_with_team
    client = as_user(t["other"].user, org=t["org"])
    assert client.get(f"{PROJECTS}/{t['project'].id}").status_code == 200
