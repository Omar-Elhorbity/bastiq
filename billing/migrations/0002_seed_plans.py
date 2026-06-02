"""Seed the default Free/Pro/Business plans so they exist in every environment.

Limits are fixed here; Stripe price ids are left blank and wired per-environment
via the `seed_plans` command / admin. Idempotent and reversible.
"""

from __future__ import annotations

from django.db import migrations

PLANS = {
    "free": {"name": "Free", "limits": {"max_projects": 3, "max_members": 3}},
    "pro": {"name": "Pro", "limits": {"max_projects": 25, "max_members": 10}},
    "business": {"name": "Business", "limits": {"max_projects": None, "max_members": None}},
}


def seed_plans(apps, schema_editor):
    Plan = apps.get_model("billing", "Plan")
    for code, spec in PLANS.items():
        Plan.objects.update_or_create(
            code=code,
            defaults={"name": spec["name"], "limits": spec["limits"], "is_active": True},
        )


def unseed_plans(apps, schema_editor):
    Plan = apps.get_model("billing", "Plan")
    Plan.objects.filter(code__in=PLANS.keys()).delete()


class Migration(migrations.Migration):
    dependencies = [("billing", "0001_initial")]
    operations = [migrations.RunPython(seed_plans, unseed_plans)]
