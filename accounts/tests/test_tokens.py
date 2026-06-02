"""Unit tests for the signed-token module (the M1 security core)."""

from __future__ import annotations

import pytest
from django.test import override_settings

from accounts.tests.factories import UserFactory
from accounts.tokens import (
    TokenError,
    generate_email_verification_token,
    generate_password_reset_token,
    read_email_verification_token,
    read_password_reset_token,
)

pytestmark = pytest.mark.django_db


# --- email verification ---------------------------------------------------- #
def test_verification_roundtrip():
    user = UserFactory()
    token = generate_email_verification_token(user)
    assert read_email_verification_token(token) == user.pk


def test_verification_token_tampering_rejected():
    user = UserFactory()
    token = generate_email_verification_token(user)
    with pytest.raises(TokenError):
        read_email_verification_token(token + "x")


def test_verification_token_expiry_rejected():
    user = UserFactory()
    token = generate_email_verification_token(user)
    with override_settings(EMAIL_VERIFICATION_TIMEOUT=-1):
        with pytest.raises(TokenError):
            read_email_verification_token(token)


def test_verification_and_reset_tokens_are_not_interchangeable():
    """A verification token must not be usable as a reset token (salt binding)."""
    user = UserFactory()
    verify_token = generate_email_verification_token(user)
    with pytest.raises(TokenError):
        read_password_reset_token(verify_token)


# --- password reset --------------------------------------------------------- #
def test_reset_roundtrip():
    user = UserFactory()
    token = generate_password_reset_token(user)
    assert read_password_reset_token(token).pk == user.pk


def test_reset_token_is_single_use_after_password_change():
    user = UserFactory()
    token = generate_password_reset_token(user)
    # Using it once is fine...
    assert read_password_reset_token(token).pk == user.pk
    # ...but once the password changes, the fingerprint rotates and it's dead.
    user.set_password("a-brand-new-password-123")
    user.save(update_fields=["password"])
    with pytest.raises(TokenError):
        read_password_reset_token(token)


def test_reset_token_invalidated_by_login(settings):
    """last_login changes on login → outstanding reset tokens are invalidated."""
    from django.utils import timezone

    user = UserFactory()
    token = generate_password_reset_token(user)
    user.last_login = timezone.now()
    user.save(update_fields=["last_login"])
    with pytest.raises(TokenError):
        read_password_reset_token(token)


def test_reset_token_expiry_rejected():
    user = UserFactory()
    token = generate_password_reset_token(user)
    with override_settings(PASSWORD_RESET_TIMEOUT=-1):
        with pytest.raises(TokenError):
            read_password_reset_token(token)


def test_reset_token_for_deleted_user_rejected():
    user = UserFactory()
    token = generate_password_reset_token(user)
    user.delete()
    with pytest.raises(TokenError):
        read_password_reset_token(token)


# --- malformed (validly-signed but wrong-shaped) payloads ------------------- #
def test_validly_signed_but_uidless_tokens_rejected():
    from django.core import signing

    from accounts.tokens import EMAIL_VERIFY_SALT, PASSWORD_RESET_SALT

    verify = signing.dumps({"nope": 1}, salt=EMAIL_VERIFY_SALT)
    reset = signing.dumps({"fp": "x"}, salt=PASSWORD_RESET_SALT)
    with pytest.raises(TokenError):
        read_email_verification_token(verify)
    with pytest.raises(TokenError):
        read_password_reset_token(reset)
