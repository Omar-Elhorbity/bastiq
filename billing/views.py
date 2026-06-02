"""Billing endpoints: plans, subscription, checkout, portal, and the webhook.

Org-context endpoints resolve the active org via ``IsOrganizationMember`` (the
``X-Organization-ID`` header); checkout/portal additionally require Owner. The
webhook is PUBLIC, signature-verified, and idempotent — it is the source of
truth for subscription state, never the success redirect.
"""

from __future__ import annotations

import stripe
from django.db import transaction
from drf_spectacular.utils import OpenApiParameter, extend_schema, inline_serializer
from rest_framework import generics, serializers, status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from billing import stripe_client
from billing.models import Plan, Subscription, WebhookEvent
from billing.permissions import IsOrganizationOwner
from billing.serializers import CheckoutSerializer, PlanSerializer, SubscriptionSerializer
from billing.webhooks import handle_event
from core.permissions import ORG_ID_HEADER, IsOrganizationMember

_ORG_HEADER_PARAM = OpenApiParameter(
    name=ORG_ID_HEADER,
    location=OpenApiParameter.HEADER,
    required=True,
    type=int,
    description="Active organization id. Must be an org you're a member of.",
)


@extend_schema(tags=["billing"])
class PlansView(generics.ListAPIView):
    """List active plans (any authenticated user)."""

    serializer_class = PlanSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = None

    def get_queryset(self):
        return Plan.objects.filter(is_active=True)


@extend_schema(
    tags=["billing"], parameters=[_ORG_HEADER_PARAM], responses={200: SubscriptionSerializer}
)
class SubscriptionView(APIView):
    """The active organization's current subscription (any member)."""

    permission_classes = [IsAuthenticated, IsOrganizationMember]

    def get(self, request):
        subscription = Subscription.objects.filter(organization=request.organization).first()
        if subscription is None:
            return Response({"detail": "No subscription for this organization."}, status=404)
        return Response(SubscriptionSerializer(subscription).data)


@extend_schema(
    tags=["billing"],
    parameters=[_ORG_HEADER_PARAM],
    request=CheckoutSerializer,
    responses={
        200: inline_serializer("CheckoutResponse", {"checkout_url": serializers.URLField()})
    },
)
class CheckoutView(APIView):
    """Create a Stripe Checkout session for a plan (owner only)."""

    permission_classes = [IsAuthenticated, IsOrganizationMember, IsOrganizationOwner]

    def post(self, request):
        serializer = CheckoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        plan = Plan.objects.filter(
            code=serializer.validated_data["plan_code"], is_active=True
        ).first()
        if plan is None:
            raise ValidationError({"plan_code": "Unknown plan."})
        if not plan.stripe_price_id:
            raise ValidationError({"plan_code": "This plan is not available for checkout."})

        org = request.organization
        subscription = Subscription.objects.filter(organization=org).first()
        if subscription is None:
            raise ValidationError("Billing is not set up for this organization.")
        customer_id = stripe_client.ensure_customer(subscription, org)
        url = stripe_client.create_checkout_session(
            customer_id=customer_id,
            price_id=plan.stripe_price_id,
            organization_id=org.id,
            plan_code=plan.code,
        )
        return Response({"checkout_url": url})


@extend_schema(
    tags=["billing"],
    parameters=[_ORG_HEADER_PARAM],
    request=None,
    responses={200: inline_serializer("PortalResponse", {"portal_url": serializers.URLField()})},
)
class PortalView(APIView):
    """Create a Stripe customer-portal session (owner only)."""

    permission_classes = [IsAuthenticated, IsOrganizationMember, IsOrganizationOwner]

    def post(self, request):
        subscription = Subscription.objects.filter(organization=request.organization).first()
        if subscription is None or not subscription.stripe_customer_id:
            raise ValidationError("No billing customer yet — subscribe first.")
        url = stripe_client.create_portal_session(customer_id=subscription.stripe_customer_id)
        return Response({"portal_url": url})


@extend_schema(
    tags=["billing"],
    request=None,
    responses={200: inline_serializer("WebhookAck", {"detail": serializers.CharField()})},
)
class WebhookView(APIView):
    """Stripe webhook: verify signature → dedupe (idempotent) → map state.

    Public and unauthenticated by design; trust comes from the signature.
    """

    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        payload = request.body  # raw bytes — required for signature verification
        signature = request.META.get("HTTP_STRIPE_SIGNATURE", "")
        try:
            event = stripe_client.construct_event(payload, signature)
        except (ValueError, stripe.error.SignatureVerificationError):
            return Response({"detail": "Invalid signature."}, status=status.HTTP_400_BAD_REQUEST)

        # Record + process atomically: a duplicate delivery is a no-op, and if
        # processing fails the ledger row rolls back so Stripe's retry reprocesses.
        with transaction.atomic():
            _event, created = WebhookEvent.objects.get_or_create(
                stripe_event_id=event["id"], defaults={"type": event.get("type", "")}
            )
            if not created:
                return Response({"detail": "Already processed."}, status=status.HTTP_200_OK)
            handle_event(event)

        return Response({"detail": "ok"}, status=status.HTTP_200_OK)
