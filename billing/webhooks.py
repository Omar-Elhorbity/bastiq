"""Stripe webhook handlers — map verified events to local Subscription state.

The webhook is the source of truth (never the success redirect). The view
verifies the signature and dedupes via WebhookEvent; this module does the state
mapping. Handlers are defensive: an event we can't tie to a local subscription
is acknowledged (so Stripe stops retrying) but otherwise ignored.
"""

from __future__ import annotations

import logging

from django.utils import timezone

from billing.models import FREE_PLAN_CODE, Plan, Subscription, SubscriptionStatus

logger = logging.getLogger("bastiq")

_STATUS_MAP = {
    "active": SubscriptionStatus.ACTIVE,
    "trialing": SubscriptionStatus.ACTIVE,
    "past_due": SubscriptionStatus.PAST_DUE,
    "unpaid": SubscriptionStatus.PAST_DUE,
    "canceled": SubscriptionStatus.CANCELED,
    "incomplete": SubscriptionStatus.INCOMPLETE,
    "incomplete_expired": SubscriptionStatus.CANCELED,
}


def _ts_to_dt(value):
    if not value:
        return None
    return timezone.datetime.fromtimestamp(int(value), tz=timezone.get_current_timezone())


def _org_id(obj) -> str | None:
    metadata = obj.get("metadata") or {}
    return metadata.get("organization_id")


def _find_subscription(obj, *, subscription_id=None, customer_id=None) -> Subscription | None:
    org_id = _org_id(obj)
    if org_id:
        sub = Subscription.objects.filter(organization_id=org_id).first()
        if sub:
            return sub
    if subscription_id:
        sub = Subscription.objects.filter(stripe_subscription_id=subscription_id).first()
        if sub:
            return sub
    if customer_id:
        return Subscription.objects.filter(stripe_customer_id=customer_id).first()
    return None


def _plan_for_price(price_id):
    if not price_id:
        return None
    return Plan.objects.filter(stripe_price_id=price_id, is_active=True).first()


def handle_checkout_completed(obj) -> None:
    sub = _find_subscription(obj, customer_id=obj.get("customer"))
    if sub is None:
        logger.warning("checkout.session.completed for unknown org: %s", obj.get("id"))
        return
    sub.stripe_customer_id = obj.get("customer") or sub.stripe_customer_id
    sub.stripe_subscription_id = obj.get("subscription") or sub.stripe_subscription_id
    metadata = obj.get("metadata") or {}
    plan = Plan.objects.filter(code=metadata.get("plan_code"), is_active=True).first()
    if plan is not None:
        sub.plan = plan
    sub.status = SubscriptionStatus.ACTIVE
    sub.save()


def handle_subscription_updated(obj) -> None:
    sub = _find_subscription(obj, subscription_id=obj.get("id"), customer_id=obj.get("customer"))
    if sub is None:
        logger.warning("customer.subscription.updated for unknown subscription: %s", obj.get("id"))
        return
    if obj.get("id"):
        sub.stripe_subscription_id = obj["id"]
    sub.status = _STATUS_MAP.get(obj.get("status"), sub.status)
    sub.current_period_end = _ts_to_dt(obj.get("current_period_end")) or sub.current_period_end
    try:
        price_id = obj["items"]["data"][0]["price"]["id"]
    except (KeyError, IndexError, TypeError):
        price_id = None
    plan = _plan_for_price(price_id)
    if plan is not None:
        sub.plan = plan
    sub.save()


def handle_subscription_deleted(obj) -> None:
    sub = _find_subscription(obj, subscription_id=obj.get("id"), customer_id=obj.get("customer"))
    if sub is None:
        return
    sub.status = SubscriptionStatus.CANCELED
    # Downgrade to Free so limits revert when a paid subscription ends. NOTE: by
    # design we never delete a customer's existing data on downgrade — an org
    # that's now over the Free cap keeps its resources but can't create new ones
    # until it's back under the limit (limits are enforced at creation time).
    free = Plan.objects.filter(code=FREE_PLAN_CODE).first()
    if free is not None:
        sub.plan = free
    sub.stripe_subscription_id = ""
    sub.save()


def handle_invoice_payment_failed(obj) -> None:
    sub = _find_subscription(
        obj, subscription_id=obj.get("subscription"), customer_id=obj.get("customer")
    )
    if sub is None:
        return
    sub.status = SubscriptionStatus.PAST_DUE
    sub.save(update_fields=["status", "updated_at"])


_HANDLERS = {
    "checkout.session.completed": handle_checkout_completed,
    "customer.subscription.updated": handle_subscription_updated,
    "customer.subscription.deleted": handle_subscription_deleted,
    "invoice.payment_failed": handle_invoice_payment_failed,
}


def handle_event(event) -> None:
    """Dispatch a verified Stripe event to its handler (no-op if unhandled)."""
    handler = _HANDLERS.get(event.get("type"))
    if handler is None:
        return
    obj = (event.get("data") or {}).get("object") or {}
    handler(obj)
