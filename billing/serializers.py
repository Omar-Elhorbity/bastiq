"""Billing serializers."""

from __future__ import annotations

from rest_framework import serializers

from billing.models import Plan, Subscription


class PlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = Plan
        fields = ["code", "name", "limits"]
        read_only_fields = fields


class SubscriptionSerializer(serializers.ModelSerializer):
    plan = PlanSerializer(read_only=True)

    class Meta:
        model = Subscription
        fields = ["plan", "status", "current_period_end", "updated_at"]
        read_only_fields = fields


class CheckoutSerializer(serializers.Serializer):
    plan_code = serializers.CharField()
