"""End-to-end auth API tests: register, verify, login, refresh, reset, /me."""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.test import override_settings

from accounts.tests.factories import UserFactory

pytestmark = pytest.mark.django_db

User = get_user_model()

REGISTER = "/api/auth/register"
VERIFY = "/api/auth/verify-email"
LOGIN = "/api/auth/login"
REFRESH = "/api/auth/token/refresh"
RESET = "/api/auth/password-reset"
RESET_CONFIRM = "/api/auth/password-reset/confirm"
ME = "/api/auth/me"

STRONG_PW = "Str0ng-Passw0rd!"


def _extract_token(body: str) -> str:
    """Pull the standalone signed token line out of an email body."""
    for raw in body.splitlines():
        line = raw.strip()
        if line and " " not in line and not line.startswith("http") and line.count(":") >= 2:
            return line
    raise AssertionError(f"no token found in email body:\n{body}")


# --- registration ----------------------------------------------------------- #
def test_register_creates_unverified_user_and_sends_email(api_client, mailoutbox):
    resp = api_client.post(
        REGISTER, {"email": "Jane@Example.com", "password": STRONG_PW, "name": "Jane Doe"}
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["email"] == "jane@example.com"  # normalised
    assert body["is_email_verified"] is False
    assert "password" not in body
    assert body["first_name"] == "Jane" and body["last_name"] == "Doe"

    user = User.objects.get(email="jane@example.com")
    assert user.is_email_verified is False
    assert len(mailoutbox) == 1
    assert mailoutbox[0].to == ["jane@example.com"]


def test_register_rejects_duplicate_email_case_insensitively(api_client):
    UserFactory(email="dup@example.com")
    resp = api_client.post(REGISTER, {"email": "DUP@example.com", "password": STRONG_PW})
    assert resp.status_code == 400
    assert "email" in resp.json()


def test_register_rejects_weak_password(api_client):
    resp = api_client.post(REGISTER, {"email": "weak@example.com", "password": "123"})
    assert resp.status_code == 400
    assert "password" in resp.json()


# --- verification ------------------------------------------------------------ #
def test_verify_email_full_flow(api_client, mailoutbox):
    api_client.post(REGISTER, {"email": "v@example.com", "password": STRONG_PW})
    token = _extract_token(mailoutbox[0].body)

    resp = api_client.post(VERIFY, {"token": token})
    assert resp.status_code == 200
    assert User.objects.get(email="v@example.com").is_email_verified is True


def test_verify_email_is_idempotent(api_client, mailoutbox):
    api_client.post(REGISTER, {"email": "v2@example.com", "password": STRONG_PW})
    token = _extract_token(mailoutbox[0].body)
    assert api_client.post(VERIFY, {"token": token}).status_code == 200
    # Second use still succeeds (no error), account stays verified.
    assert api_client.post(VERIFY, {"token": token}).status_code == 200


def test_verify_email_rejects_garbage_token(api_client):
    resp = api_client.post(VERIFY, {"token": "not-a-real-token"})
    assert resp.status_code == 400


# --- login / refresh --------------------------------------------------------- #
def test_login_returns_token_pair_with_claims(api_client):
    UserFactory(email="login@example.com", password=STRONG_PW)
    resp = api_client.post(LOGIN, {"email": "login@example.com", "password": STRONG_PW})
    assert resp.status_code == 200
    data = resp.json()
    assert "access" in data and "refresh" in data

    from rest_framework_simplejwt.tokens import AccessToken

    claims = AccessToken(data["access"])
    assert claims["email"] == "login@example.com"
    assert claims["is_email_verified"] is True


def test_login_wrong_password_is_401(api_client):
    UserFactory(email="login2@example.com", password=STRONG_PW)
    resp = api_client.post(LOGIN, {"email": "login2@example.com", "password": "wrong-pw-here"})
    assert resp.status_code == 401


def test_login_unknown_user_is_401(api_client):
    resp = api_client.post(LOGIN, {"email": "nobody@example.com", "password": STRONG_PW})
    assert resp.status_code == 401


def test_login_can_require_verified_email(api_client):
    UserFactory(email="unverified@example.com", password=STRONG_PW, is_email_verified=False)
    with override_settings(LOGIN_REQUIRE_VERIFIED_EMAIL=True):
        resp = api_client.post(LOGIN, {"email": "unverified@example.com", "password": STRONG_PW})
    assert resp.status_code == 400
    assert "verified" in str(resp.json()).lower()


def test_refresh_returns_new_access(api_client):
    UserFactory(email="ref@example.com", password=STRONG_PW)
    login = api_client.post(LOGIN, {"email": "ref@example.com", "password": STRONG_PW}).json()
    resp = api_client.post(REFRESH, {"refresh": login["refresh"]})
    assert resp.status_code == 200
    assert "access" in resp.json()


# --- password reset ---------------------------------------------------------- #
def test_password_reset_request_is_enumeration_safe(api_client, mailoutbox):
    UserFactory(email="real@example.com", password=STRONG_PW)

    r1 = api_client.post(RESET, {"email": "real@example.com"})
    r2 = api_client.post(RESET, {"email": "ghost@example.com"})

    assert r1.status_code == r2.status_code == 202
    assert r1.json() == r2.json()  # identical response
    # Only the real account receives mail.
    assert len(mailoutbox) == 1
    assert mailoutbox[0].to == ["real@example.com"]


def test_password_reset_confirm_changes_password(api_client, mailoutbox):
    UserFactory(email="rp@example.com", password=STRONG_PW)
    api_client.post(RESET, {"email": "rp@example.com"})
    token = _extract_token(mailoutbox[0].body)

    new_pw = "Even-Str0nger-PW!"
    resp = api_client.post(RESET_CONFIRM, {"token": token, "new_password": new_pw})
    assert resp.status_code == 200

    # Old password fails, new one works.
    assert (
        api_client.post(LOGIN, {"email": "rp@example.com", "password": STRONG_PW}).status_code
        == 401
    )
    assert (
        api_client.post(LOGIN, {"email": "rp@example.com", "password": new_pw}).status_code == 200
    )


def test_password_reset_token_is_single_use(api_client, mailoutbox):
    UserFactory(email="su@example.com", password=STRONG_PW)
    api_client.post(RESET, {"email": "su@example.com"})
    token = _extract_token(mailoutbox[0].body)

    assert (
        api_client.post(
            RESET_CONFIRM, {"token": token, "new_password": "First-PW-12345!"}
        ).status_code
        == 200
    )
    # Reusing the same token after the password changed is rejected.
    resp = api_client.post(RESET_CONFIRM, {"token": token, "new_password": "Second-PW-12345!"})
    assert resp.status_code == 400


def test_password_reset_confirm_rejects_weak_password(api_client, mailoutbox):
    UserFactory(email="wk@example.com", password=STRONG_PW)
    api_client.post(RESET, {"email": "wk@example.com"})
    token = _extract_token(mailoutbox[0].body)
    resp = api_client.post(RESET_CONFIRM, {"token": token, "new_password": "123"})
    assert resp.status_code == 400
    assert "new_password" in resp.json()


def test_password_reset_confirm_rejects_bad_token(api_client):
    resp = api_client.post(RESET_CONFIRM, {"token": "garbage", "new_password": STRONG_PW})
    assert resp.status_code == 400


def test_password_reset_confirm_rejects_expired_token(api_client, mailoutbox):
    UserFactory(email="exp@example.com", password=STRONG_PW)
    api_client.post(RESET, {"email": "exp@example.com"})
    token = _extract_token(mailoutbox[0].body)
    # Expire the token end-to-end through the API (not just the token module).
    with override_settings(PASSWORD_RESET_TIMEOUT=-1):
        resp = api_client.post(RESET_CONFIRM, {"token": token, "new_password": "Fresh-PW-12345!"})
    assert resp.status_code == 400


def test_password_reset_revokes_existing_refresh_tokens(api_client, mailoutbox):
    """After a reset, previously-issued refresh tokens are blacklisted."""
    UserFactory(email="rev@example.com", password=STRONG_PW)
    login = api_client.post(LOGIN, {"email": "rev@example.com", "password": STRONG_PW}).json()
    old_refresh = login["refresh"]

    api_client.post(RESET, {"email": "rev@example.com"})
    token = _extract_token(mailoutbox[0].body)
    assert (
        api_client.post(
            RESET_CONFIRM, {"token": token, "new_password": "Rotated-PW-12345!"}
        ).status_code
        == 200
    )

    # The refresh token minted before the reset is now dead.
    assert api_client.post(REFRESH, {"refresh": old_refresh}).status_code == 401


# --- /me --------------------------------------------------------------------- #
def test_me_requires_auth(api_client):
    assert api_client.get(ME).status_code == 401


def test_me_returns_current_user(auth_client, user):
    resp = auth_client.get(ME)
    assert resp.status_code == 200
    assert resp.json()["email"] == user.email


# --- the email-token extraction test helper itself --------------------------- #
def test_extract_token_picks_the_standalone_token_line():
    body = (
        "Hi there,\n\n"
        "Open this link:\nhttp://localhost:8000/verify-email?token=abc:def:ghi\n\n"
        "Or POST this token:\nabc123:DEF456:ghi-_789\n\n"
        "Expires soon.\n"
    )
    assert _extract_token(body) == "abc123:DEF456:ghi-_789"


def test_extract_token_raises_when_absent():
    with pytest.raises(AssertionError):
        _extract_token("No token anywhere in here.\nJust prose.\n")
