"""Thin wrapper around the Stripe SDK.

All Stripe network calls funnel through here so they're easy to configure and to
mock in tests. The API key is read per call so settings overrides take effect.
"""

from __future__ import annotations

import stripe
from django.conf import settings
from rest_framework.exceptions import APIException


class BillingNotConfigured(APIException):
    status_code = 503
    default_detail = "Billing is not configured on this server."
    default_code = "billing_not_configured"


def _client() -> None:
    if not settings.STRIPE_SECRET_KEY:
        raise BillingNotConfigured()
    stripe.api_key = settings.STRIPE_SECRET_KEY


def ensure_customer(subscription, organization) -> str:
    """Return the org's Stripe customer id, creating the customer if needed."""
    if subscription.stripe_customer_id:
        return subscription.stripe_customer_id
    _client()
    customer = stripe.Customer.create(
        name=organization.name,
        metadata={"organization_id": str(organization.id)},
    )
    subscription.stripe_customer_id = customer["id"]
    subscription.save(update_fields=["stripe_customer_id"])
    return customer["id"]


def create_checkout_session(*, customer_id, price_id, organization_id, plan_code) -> str:
    _client()
    metadata = {"organization_id": str(organization_id), "plan_code": plan_code}
    session = stripe.checkout.Session.create(
        mode="subscription",
        customer=customer_id,
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=settings.BILLING_SUCCESS_URL,
        cancel_url=settings.BILLING_CANCEL_URL,
        metadata=metadata,
        # Stamp the org on the subscription too, so subscription.* webhook
        # events carry it without a separate lookup.
        subscription_data={"metadata": {"organization_id": str(organization_id)}},
    )
    return session["url"]


def create_portal_session(*, customer_id) -> str:
    _client()
    session = stripe.billing_portal.Session.create(
        customer=customer_id,
        return_url=settings.BILLING_PORTAL_RETURN_URL,
    )
    return session["url"]


def construct_event(payload: bytes, signature: str):
    """Verify the Stripe-Signature and return the event (raises on bad sig)."""
    if not settings.STRIPE_WEBHOOK_SECRET:
        raise BillingNotConfigured()
    return stripe.Webhook.construct_event(payload, signature, settings.STRIPE_WEBHOOK_SECRET)
