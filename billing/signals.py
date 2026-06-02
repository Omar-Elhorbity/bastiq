"""Give every new organization a Free subscription.

Lives in billing (not organizations) so the dependency points one way:
billing → organizations. If the Free plan isn't seeded yet, we skip silently;
limit checks fall back to Free defaults anyway.
"""

from __future__ import annotations

import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from organizations.models import Organization

logger = logging.getLogger("bastiq")


@receiver(post_save, sender=Organization, dispatch_uid="billing.create_free_subscription")
def create_free_subscription(sender, instance, created, **kwargs):
    if not created:
        return
    from billing.models import FREE_PLAN_CODE, Plan, Subscription

    free = Plan.objects.filter(code=FREE_PLAN_CODE).first()
    if free is None:
        logger.warning("No Free plan seeded; organization %s has no subscription.", instance.id)
        return
    Subscription.objects.get_or_create(organization=instance, defaults={"plan": free})
