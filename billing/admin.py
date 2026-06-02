"""Admin for billing models."""

from __future__ import annotations

from django.contrib import admin

from billing.models import Plan, Subscription, WebhookEvent


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "stripe_price_id", "is_active")
    list_filter = ("is_active",)
    search_fields = ("code", "name", "stripe_price_id")


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ("organization", "plan", "status", "current_period_end", "updated_at")
    list_filter = ("status", "plan")
    search_fields = ("organization__name", "stripe_customer_id", "stripe_subscription_id")
    autocomplete_fields = ("organization", "plan")
    readonly_fields = ("updated_at",)


@admin.register(WebhookEvent)
class WebhookEventAdmin(admin.ModelAdmin):
    list_display = ("stripe_event_id", "type", "processed_at")
    search_fields = ("stripe_event_id", "type")
    readonly_fields = ("stripe_event_id", "type", "processed_at")
