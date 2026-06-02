"""Shared pytest fixtures.

The deterministic test *environment* is configured in ``bastiq/test_settings.py``
(selected via ``DJANGO_SETTINGS_MODULE = bastiq.test_settings`` in pyproject),
which sets env defaults before importing the real settings. This module holds
the shared fixtures.
"""

from __future__ import annotations

import pytest


@pytest.fixture
def api_client():
    """Unauthenticated DRF test client."""
    from rest_framework.test import APIClient

    return APIClient()


@pytest.fixture
def user(db):
    """A verified, active user."""
    from django.contrib.auth import get_user_model

    return get_user_model().objects.create_user(
        email="user@example.com",
        password="sup3r-secret-pw",
        is_email_verified=True,
    )


@pytest.fixture
def auth_client(api_client, user):
    """DRF client carrying a valid JWT for ``user``."""
    from rest_framework_simplejwt.tokens import RefreshToken

    access = RefreshToken.for_user(user).access_token
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
    return api_client
