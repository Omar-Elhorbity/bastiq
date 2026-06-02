"""The project exception handler must never leak HTML/tracebacks in prod."""

from __future__ import annotations

from rest_framework.exceptions import NotFound, ValidationError

from core.exceptions import api_exception_handler


def _context():
    return {"view": None, "request": None, "args": (), "kwargs": {}}


def test_handled_drf_error_keeps_native_shape():
    response = api_exception_handler(NotFound(), _context())
    assert response is not None
    assert response.status_code == 404
    assert "detail" in response.data


def test_validation_error_field_details_preserved():
    response = api_exception_handler(ValidationError({"email": ["required"]}), _context())
    assert response is not None
    assert response.status_code == 400
    assert response.data["email"] == ["required"]


def test_unhandled_exception_returns_opaque_500_in_production(settings):
    settings.DEBUG = False
    response = api_exception_handler(ValueError("boom"), _context())
    assert response is not None
    assert response.status_code == 500
    assert response.data == {"detail": "Internal server error."}


def test_unhandled_exception_passes_through_in_debug(settings):
    settings.DEBUG = True
    # Returning None lets Django render its technical 500 page for developers.
    assert api_exception_handler(ValueError("boom"), _context()) is None
