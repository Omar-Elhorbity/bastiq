"""Shared, app-agnostic views."""

from __future__ import annotations

from django.http import HttpRequest, JsonResponse
from django.views.decorators.http import require_GET


@require_GET
def healthz(_request: HttpRequest) -> JsonResponse:
    """Liveness probe.

    Intentionally dependency-free (no DB/Redis hit) so it answers fast and is
    safe to hammer from a load balancer. Public, no auth, no throttling.
    """
    return JsonResponse({"status": "ok"})
