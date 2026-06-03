"""Shared, app-agnostic views."""

from __future__ import annotations

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET


@require_GET
def healthz(_request: HttpRequest) -> JsonResponse:
    """Liveness probe.

    Intentionally dependency-free (no DB/Redis hit) so it answers fast and is
    safe to hammer from a load balancer. Public, no auth, no throttling.
    """
    return JsonResponse({"status": "ok"})


@require_GET
def landing(request: HttpRequest) -> HttpResponse:
    """Public site root: an editorial landing page pointing at the live API docs,
    source, health, and admin. Saves the bare domain from being a 404.

    Rendered from ``core/templates/landing.html`` — a single self-contained
    template (inline styles, no static-pipeline dependency).
    """
    return render(request, "landing.html")
