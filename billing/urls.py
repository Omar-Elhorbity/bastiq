"""Billing routes, mounted under /api/billing/ by the root urlconf."""

from __future__ import annotations

from django.urls import path

from billing.views import (
    CheckoutView,
    PlansView,
    PortalView,
    SubscriptionView,
    WebhookView,
)

app_name = "billing"

urlpatterns = [
    path("plans", PlansView.as_view(), name="plans"),
    path("subscription", SubscriptionView.as_view(), name="subscription"),
    path("checkout", CheckoutView.as_view(), name="checkout"),
    path("portal", PortalView.as_view(), name="portal"),
    path("webhook", WebhookView.as_view(), name="webhook"),
]
