"""Billing models: Plan, Subscription, and the WebhookEvent idempotency ledger."""

from __future__ import annotations

from django.db import models

from organizations.models import Organization

# Default plan catalogue (seeded by a data migration + the seed_plans command).
# A limit of None means "unlimited". max_members counts every membership
# (including the Owner).
FREE_PLAN_CODE = "free"
DEFAULT_PLANS = {
    "free": {"name": "Free", "limits": {"max_projects": 3, "max_members": 3}},
    "pro": {"name": "Pro", "limits": {"max_projects": 25, "max_members": 10}},
    "business": {"name": "Business", "limits": {"max_projects": None, "max_members": None}},
}


class Plan(models.Model):
    code = models.CharField(max_length=32, unique=True)  # free | pro | business
    name = models.CharField(max_length=64)
    stripe_price_id = models.CharField(max_length=255, blank=True)
    limits = models.JSONField(default=dict)  # {"max_members": 3, "max_projects": 3}
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["id"]

    def __str__(self) -> str:
        return self.name

    def limit(self, key: str) -> int | None:
        """Return the numeric cap for ``key``, or None for unlimited."""
        return self.limits.get(key)


class SubscriptionStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    PAST_DUE = "past_due", "Past due"
    CANCELED = "canceled", "Canceled"
    INCOMPLETE = "incomplete", "Incomplete"


class Subscription(models.Model):
    organization = models.OneToOneField(
        Organization, on_delete=models.CASCADE, related_name="subscription"
    )
    # PROTECT: a plan in use can't be deleted out from under a subscription.
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT, related_name="subscriptions")
    stripe_customer_id = models.CharField(max_length=255, blank=True)
    stripe_subscription_id = models.CharField(max_length=255, blank=True)
    status = models.CharField(
        max_length=32, choices=SubscriptionStatus.choices, default=SubscriptionStatus.ACTIVE
    )
    current_period_end = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["stripe_subscription_id"]),
            models.Index(fields=["stripe_customer_id"]),
        ]

    def __str__(self) -> str:
        return f"{self.organization_id} → {self.plan.code} ({self.status})"


class WebhookEvent(models.Model):
    """Idempotency ledger — a Stripe event is processed at most once."""

    stripe_event_id = models.CharField(max_length=255, unique=True)
    type = models.CharField(max_length=64)
    processed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-processed_at"]

    def __str__(self) -> str:
        return f"{self.type} {self.stripe_event_id}"
