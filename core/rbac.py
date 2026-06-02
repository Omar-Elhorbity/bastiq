"""Role-based access control — the permission matrix, as code.

Roles are ranked Owner(3) > Admin(2) > Member(1). The matrix the code enforces:

| Action                               | Owner | Admin            | Member |
|--------------------------------------|-------|------------------|--------|
| Read org / list members / invites    |  ✓    | ✓                | ✓ (read org/members; invites: ✗) |
| Update org (name)                    |  ✓    | ✓                | ✗      |
| Delete org                           |  ✓    | ✗                | ✗      |
| Invite member (role ≤ own rank)      |  ✓    | ✓ (not as Owner) | ✗      |
| Change a member's role               |  ✓    | ✓ (targets ≤ Admin; assigns ≤ Admin) | ✗ |
| Remove a member                      |  ✓    | ✓ (targets ≤ Admin) | ✗   |
| Read/create project                  |  ✓    | ✓                | ✓      |
| Update/delete project                |  ✓    | ✓                | creator only |

Two universal guards on member management:
- **No privilege escalation:** you can never grant a role higher than your own.
- **No ownerless org:** you can't demote or remove the last remaining Owner.

"below Owner" is read literally: an Admin may manage any membership whose rank is
≤ their own (Members and other Admins) but never an Owner, and may assign roles
up to their own rank (Member/Admin) but never Owner.
"""

from __future__ import annotations

from organizations.models import Membership, Role

MANAGER_ROLES = frozenset({Role.OWNER, Role.ADMIN})


def can_manage_member(actor_role: str, target_role: str) -> bool:
    """True if an actor may change/remove a membership currently at target_role."""
    if actor_role not in MANAGER_ROLES:
        return False
    return Role.rank(target_role) <= Role.rank(actor_role)


def can_assign_role(actor_role: str, new_role: str) -> bool:
    """True if an actor may grant new_role (no escalation above their own rank)."""
    if actor_role not in MANAGER_ROLES:
        return False
    return Role.rank(new_role) <= Role.rank(actor_role)


def is_last_owner(membership: Membership) -> bool:
    """True if this membership is the only Owner of its organization."""
    if membership.role != Role.OWNER:
        return False
    return (
        Membership.objects.filter(
            organization_id=membership.organization_id, role=Role.OWNER
        ).count()
        <= 1
    )
