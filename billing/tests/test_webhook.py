"""Stripe webhook: signature verification, idempotency, and state mapping."""

from __future__ import annotations

import pytest
import stripe

from billing import stripe_client
from billing.models import Plan, Subscription, SubscriptionStatus, WebhookEvent
from organizations.models import Role
from organizations.tests.factories import MembershipFactory

pytestmark = pytest.mark.django_db

WEBHOOK = "/api/billing/webhook"


def _post(api_client, monkeypatch, event):
    monkeypatch.setattr(stripe_client, "construct_event", lambda payload, sig: event)
    return api_client.post(
        WEBHOOK, data=b"{}", content_type="application/json", HTTP_STRIPE_SIGNATURE="t=1,v1=sig"
    )


def _org():
    owner = MembershipFactory(role=Role.OWNER)
    return owner.organization


def test_invalid_signature_is_rejected(api_client, monkeypatch):
    def _raise(payload, sig):
        raise stripe.error.SignatureVerificationError("bad", sig)

    monkeypatch.setattr(stripe_client, "construct_event", _raise)
    resp = api_client.post(WEBHOOK, data=b"{}", content_type="application/json")
    assert resp.status_code == 400
    assert WebhookEvent.objects.count() == 0


def test_checkout_completed_upgrades_plan(api_client, monkeypatch):
    org = _org()
    event = {
        "id": "evt_checkout",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_1",
                "customer": "cus_1",
                "subscription": "sub_1",
                "metadata": {"organization_id": str(org.id), "plan_code": "pro"},
            }
        },
    }
    assert _post(api_client, monkeypatch, event).status_code == 200
    sub = Subscription.objects.get(organization=org)
    assert sub.plan.code == "pro"
    assert sub.status == SubscriptionStatus.ACTIVE
    assert sub.stripe_customer_id == "cus_1"
    assert sub.stripe_subscription_id == "sub_1"


def test_duplicate_delivery_is_processed_once(api_client, monkeypatch):
    org = _org()
    first = {
        "id": "evt_dup",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "customer": "c",
                "subscription": "s",
                "metadata": {"organization_id": str(org.id), "plan_code": "pro"},
            }
        },
    }
    # Same event id, but pretends to set a different plan.
    second = {
        "id": "evt_dup",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "customer": "c",
                "subscription": "s",
                "metadata": {"organization_id": str(org.id), "plan_code": "business"},
            }
        },
    }
    assert _post(api_client, monkeypatch, first).status_code == 200
    assert _post(api_client, monkeypatch, second).status_code == 200  # ack, but not reprocessed

    assert WebhookEvent.objects.filter(stripe_event_id="evt_dup").count() == 1
    # The second (business) delivery was ignored → plan stays pro.
    assert Subscription.objects.get(organization=org).plan.code == "pro"


def test_subscription_updated_maps_price_and_status(api_client, monkeypatch):
    org = _org()
    Plan.objects.filter(code="pro").update(stripe_price_id="price_pro")
    event = {
        "id": "evt_updated",
        "type": "customer.subscription.updated",
        "data": {
            "object": {
                "id": "sub_9",
                "customer": "cus_9",
                "status": "active",
                "current_period_end": 1893456000,
                "metadata": {"organization_id": str(org.id)},
                "items": {"data": [{"price": {"id": "price_pro"}}]},
            }
        },
    }
    assert _post(api_client, monkeypatch, event).status_code == 200
    sub = Subscription.objects.get(organization=org)
    assert sub.plan.code == "pro"
    assert sub.current_period_end is not None


def test_subscription_deleted_downgrades_to_free(api_client, monkeypatch):
    org = _org()
    sub = org.subscription
    sub.plan = Plan.objects.get(code="pro")
    sub.stripe_subscription_id = "sub_del"
    sub.save()
    event = {
        "id": "evt_deleted",
        "type": "customer.subscription.deleted",
        "data": {
            "object": {
                "id": "sub_del",
                "customer": "cus_d",
                "metadata": {"organization_id": str(org.id)},
            }
        },
    }
    assert _post(api_client, monkeypatch, event).status_code == 200
    sub.refresh_from_db()
    assert sub.status == SubscriptionStatus.CANCELED
    assert sub.plan.code == "free"


def test_invoice_payment_failed_sets_past_due(api_client, monkeypatch):
    org = _org()
    sub = org.subscription
    sub.stripe_subscription_id = "sub_pf"
    sub.save(update_fields=["stripe_subscription_id"])
    event = {
        "id": "evt_failed",
        "type": "invoice.payment_failed",
        "data": {"object": {"id": "in_1", "customer": "cus_pf", "subscription": "sub_pf"}},
    }
    assert _post(api_client, monkeypatch, event).status_code == 200
    sub.refresh_from_db()
    assert sub.status == SubscriptionStatus.PAST_DUE


def test_unknown_event_type_is_acknowledged(api_client, monkeypatch):
    event = {"id": "evt_unknown", "type": "customer.created", "data": {"object": {}}}
    assert _post(api_client, monkeypatch, event).status_code == 200
    assert WebhookEvent.objects.filter(stripe_event_id="evt_unknown").exists()


def test_webhook_requires_configuration(api_client, settings):
    # No mock + no STRIPE_WEBHOOK_SECRET → the real verifier reports "not configured".
    settings.STRIPE_WEBHOOK_SECRET = ""
    resp = api_client.post(WEBHOOK, data=b"{}", content_type="application/json")
    assert resp.status_code == 503


def test_subscription_updated_incomplete_status(api_client, monkeypatch):
    org = _org()
    event = {
        "id": "evt_incomplete",
        "type": "customer.subscription.updated",
        "data": {
            "object": {
                "id": "sub_i",
                "status": "incomplete",
                "metadata": {"organization_id": str(org.id)},
            }
        },
    }
    assert _post(api_client, monkeypatch, event).status_code == 200
    assert Subscription.objects.get(organization=org).status == SubscriptionStatus.INCOMPLETE


def test_processing_failure_rolls_back_ledger_and_allows_retry(api_client, monkeypatch):
    """If a handler raises, the WebhookEvent row rolls back so Stripe's retry
    reprocesses the event (idempotency must not swallow failed processing)."""
    import billing.webhooks

    org = _org()
    event = {
        "id": "evt_retry",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "customer": "c",
                "subscription": "s",
                "metadata": {"organization_id": str(org.id), "plan_code": "pro"},
            }
        },
    }
    monkeypatch.setattr(stripe_client, "construct_event", lambda payload, sig: event)

    # First delivery: handler blows up → 500, ledger row rolled back.
    def _boom(_event):
        raise RuntimeError("processing failed")

    monkeypatch.setattr("billing.views.handle_event", _boom)
    api_client.raise_request_exception = False
    resp = api_client.post(WEBHOOK, data=b"{}", content_type="application/json")
    assert resp.status_code == 500
    assert not WebhookEvent.objects.filter(stripe_event_id="evt_retry").exists()

    # Retry with the real handler → processed exactly once now.
    monkeypatch.setattr("billing.views.handle_event", billing.webhooks.handle_event)
    resp2 = api_client.post(WEBHOOK, data=b"{}", content_type="application/json")
    assert resp2.status_code == 200
    assert WebhookEvent.objects.filter(stripe_event_id="evt_retry").count() == 1
    assert Subscription.objects.get(organization=org).plan.code == "pro"
