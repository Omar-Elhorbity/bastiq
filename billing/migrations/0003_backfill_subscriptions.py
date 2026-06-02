"""Backfill a Free subscription for any organization created before billing
existed (the post_save signal only covers orgs created from M5 onward)."""

from __future__ import annotations

from django.db import migrations


def backfill(apps, schema_editor):
    Organization = apps.get_model("organizations", "Organization")
    Plan = apps.get_model("billing", "Plan")
    Subscription = apps.get_model("billing", "Subscription")

    free = Plan.objects.filter(code="free").first()
    if free is None:
        return
    for org in Organization.objects.filter(subscription__isnull=True):
        Subscription.objects.get_or_create(organization=org, defaults={"plan": free})


class Migration(migrations.Migration):
    dependencies = [("billing", "0002_seed_plans")]
    operations = [migrations.RunPython(backfill, migrations.RunPython.noop)]
