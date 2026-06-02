"""Idempotently create/update the Free/Pro/Business plans.

Run on deploy after migrate. Limits come from DEFAULT_PLANS; Stripe price ids are
read from the environment (STRIPE_PRICE_PRO / STRIPE_PRICE_BUSINESS) so the same
catalogue works across environments without committing ids.
"""

from __future__ import annotations

from django.conf import settings
from django.core.management.base import BaseCommand

from billing.models import DEFAULT_PLANS, Plan

_PRICE_ENV = {
    "pro": "STRIPE_PRICE_PRO",
    "business": "STRIPE_PRICE_BUSINESS",
}


class Command(BaseCommand):
    help = "Create or update the default plan catalogue (Free/Pro/Business)."

    def handle(self, *args, **options):
        for code, spec in DEFAULT_PLANS.items():
            price_id = getattr(settings, _PRICE_ENV[code], "") if code in _PRICE_ENV else ""
            defaults = {"name": spec["name"], "limits": spec["limits"], "is_active": True}
            if price_id:
                defaults["stripe_price_id"] = price_id
            plan, created = Plan.objects.update_or_create(code=code, defaults=defaults)
            verb = "Created" if created else "Updated"
            self.stdout.write(f"{verb} plan '{plan.code}' (price_id={plan.stripe_price_id or '—'})")
