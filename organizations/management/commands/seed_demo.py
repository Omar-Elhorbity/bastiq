"""Seed demo data for the proposal walkthrough (idempotent).

Creates the Acme Inc organization on the Free plan with three users
(owner/admin/member) and two projects. Re-running resets the demo passwords so
the documented credentials always work. Plans are seeded by migration; this
command ensures they exist too.
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import transaction

from organizations.models import Membership, Organization, Role
from projects.models import Project

User = get_user_model()

DEMO_PASSWORD = "BastiqDemo!23"  # noqa: S105 (documented demo credential)
DEMO_USERS = [
    ("owner@acme.test", "Olivia Owner", Role.OWNER),
    ("admin@acme.test", "Adam Admin", Role.ADMIN),
    ("member@acme.test", "Mia Member", Role.MEMBER),
]


class Command(BaseCommand):
    help = "Seed demo data: Acme Inc, three users (owner/admin/member), two projects."

    @transaction.atomic
    def handle(self, *args, **options):
        call_command("seed_plans")

        org, _ = Organization.objects.get_or_create(slug="acme-inc", defaults={"name": "Acme Inc"})

        users = {}
        for email, name, role in DEMO_USERS:
            first, _, last = name.partition(" ")
            user, _ = User.objects.get_or_create(
                email=email,
                defaults={"first_name": first, "last_name": last, "is_email_verified": True},
            )
            user.set_password(DEMO_PASSWORD)
            user.is_email_verified = True
            user.save()
            users[role] = user
            Membership.objects.get_or_create(user=user, organization=org, defaults={"role": role})
        if org.created_by_id is None:
            org.created_by = users[Role.OWNER]
            org.save(update_fields=["created_by"])

        for name in ("Website Redesign", "Mobile App"):
            Project.objects.get_or_create(
                organization=org,
                name=name,
                defaults={"created_by": users[Role.OWNER], "description": "Demo project."},
            )

        self.stdout.write(self.style.SUCCESS("Seeded demo data."))
        self.stdout.write(f"  Organization: {org.name} (X-Organization-ID: {org.id})")
        self.stdout.write(f"  Password for all demo users: {DEMO_PASSWORD}")
        for email, _name, role in DEMO_USERS:
            self.stdout.write(f"  {role:<6} {email}")
