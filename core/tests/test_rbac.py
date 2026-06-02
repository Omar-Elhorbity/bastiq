"""Unit tests for the RBAC matrix functions."""

from __future__ import annotations

import pytest

from core.rbac import can_assign_role, can_manage_member, is_last_owner
from organizations.models import Role
from organizations.tests.factories import MembershipFactory

OWNER, ADMIN, MEMBER = Role.OWNER, Role.ADMIN, Role.MEMBER


@pytest.mark.parametrize(
    ("actor", "target", "expected"),
    [
        (OWNER, OWNER, True),
        (OWNER, ADMIN, True),
        (OWNER, MEMBER, True),
        (ADMIN, OWNER, False),  # admin can't touch an owner
        (ADMIN, ADMIN, True),
        (ADMIN, MEMBER, True),
        (MEMBER, MEMBER, False),  # members can't manage anyone
        (MEMBER, OWNER, False),
    ],
)
def test_can_manage_member(actor, target, expected):
    assert can_manage_member(actor, target) is expected


@pytest.mark.parametrize(
    ("actor", "new_role", "expected"),
    [
        (OWNER, OWNER, True),
        (OWNER, ADMIN, True),
        (OWNER, MEMBER, True),
        (ADMIN, OWNER, False),  # no escalation above own rank
        (ADMIN, ADMIN, True),
        (ADMIN, MEMBER, True),
        (MEMBER, MEMBER, False),
    ],
)
def test_can_assign_role(actor, new_role, expected):
    assert can_assign_role(actor, new_role) is expected


@pytest.mark.django_db
def test_is_last_owner():
    owner = MembershipFactory(role=Role.OWNER)
    org = owner.organization
    assert is_last_owner(owner) is True

    second_owner = MembershipFactory(organization=org, role=Role.OWNER)
    assert is_last_owner(owner) is False
    assert is_last_owner(second_owner) is False

    member = MembershipFactory(organization=org, role=Role.MEMBER)
    assert is_last_owner(member) is False
