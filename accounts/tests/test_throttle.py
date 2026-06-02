"""Credential-sensitive endpoints are rate-limited (brute-force protection)."""

from __future__ import annotations

import pytest
from django.core.cache import cache
from rest_framework.throttling import ScopedRateThrottle

from accounts.tests.factories import UserFactory

pytestmark = pytest.mark.django_db

LOGIN = "/api/auth/login"
REGISTER = "/api/auth/register"
RESET = "/api/auth/password-reset"


def test_login_is_rate_limited(api_client, monkeypatch):
    UserFactory(email="brute@example.com", password="Str0ng-Passw0rd!")
    # DRF binds THROTTLE_RATES at import, so patch the rate dict directly.
    monkeypatch.setitem(ScopedRateThrottle.THROTTLE_RATES, "login", "3/min")
    cache.clear()

    payload = {"email": "brute@example.com", "password": "wrong-password"}
    statuses = [api_client.post(LOGIN, payload).status_code for _ in range(4)]

    # First 3 are processed (401 bad creds); the 4th is throttled.
    assert statuses[:3] == [401, 401, 401]
    assert statuses[3] == 429


def test_register_is_rate_limited(api_client, monkeypatch):
    monkeypatch.setitem(ScopedRateThrottle.THROTTLE_RATES, "register", "2/min")
    cache.clear()
    statuses = [
        api_client.post(
            REGISTER, {"email": f"reg{i}@example.com", "password": "Str0ng-Passw0rd!"}
        ).status_code
        for i in range(3)
    ]
    assert statuses[:2] == [201, 201]
    assert statuses[2] == 429


def test_password_reset_is_rate_limited(api_client, monkeypatch):
    monkeypatch.setitem(ScopedRateThrottle.THROTTLE_RATES, "password_reset", "2/min")
    cache.clear()
    statuses = [
        api_client.post(RESET, {"email": "whoever@example.com"}).status_code for _ in range(3)
    ]
    assert statuses[:2] == [202, 202]
    assert statuses[2] == 429
