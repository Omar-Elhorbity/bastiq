"""Project-wide DRF exception handling.

Goal: the API never leaks an HTML 500 page or a stack trace to a client in
production. Handled DRF errors keep their native shape (so field-level
validation errors remain useful); truly unhandled exceptions are logged and
returned as a generic JSON 500.
"""

from __future__ import annotations

import logging

from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

logger = logging.getLogger("bastiq")


def api_exception_handler(exc, context) -> Response | None:
    response = drf_exception_handler(exc, context)
    if response is not None:
        return response

    # DRF returned None → this is an exception it doesn't recognise (i.e. a
    # would-be HTTP 500). Log it with context for debugging.
    view = context.get("view")
    request = context.get("request")
    logger.exception(
        "Unhandled exception in %s (%s %s)",
        view.__class__.__name__ if view else "?",
        getattr(request, "method", "?"),
        getattr(request, "path", "?"),
    )

    from django.conf import settings

    # In DEBUG, return None so Django's technical 500 page (full traceback) is
    # shown to the developer. In production, fail closed with an opaque message.
    if settings.DEBUG:
        return None

    return Response({"detail": "Internal server error."}, status=500)
