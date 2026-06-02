"""Signed, expiring, table-free tokens for email verification & password reset.

Built on :mod:`django.core.signing`, which signs (HMAC with ``SECRET_KEY``) and
timestamps a JSON payload. Key properties:

* **Tamper-proof, not secret** — the payload (a user id) is readable but cannot
  be altered without invalidating the signature. No secrets are placed in it.
* **Purpose-bound** — each flow uses a distinct ``salt`` so a verification token
  can never be replayed as a password-reset token (or vice versa).
* **Expiring** — ``loads(..., max_age=...)`` rejects tokens past their TTL.
* **Single-use password resets** — the reset token embeds a fingerprint derived
  from the password hash + ``last_login``. Resetting the password (or logging
  in) changes that fingerprint, so any previously issued reset token stops
  working. This mirrors Django's built-in PasswordResetTokenGenerator.
"""

from __future__ import annotations

import hashlib
import hmac

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import signing

User = get_user_model()

EMAIL_VERIFY_SALT = "bastiq.accounts.email-verify"
PASSWORD_RESET_SALT = "bastiq.accounts.password-reset"  # noqa: S105 (signing salt, not a secret)


class TokenError(Exception):
    """Raised when a token is invalid, expired, tampered with, or unusable."""


# --------------------------------------------------------------------------- #
# Email verification
# --------------------------------------------------------------------------- #
def generate_email_verification_token(user) -> str:
    return signing.dumps({"uid": user.pk}, salt=EMAIL_VERIFY_SALT)


def read_email_verification_token(token: str) -> int:
    """Return the user id encoded in a valid verification token, else raise."""
    try:
        data = signing.loads(
            token, salt=EMAIL_VERIFY_SALT, max_age=settings.EMAIL_VERIFICATION_TIMEOUT
        )
    except signing.BadSignature as exc:  # includes SignatureExpired
        raise TokenError("Invalid or expired verification token.") from exc
    uid = data.get("uid")
    if uid is None:
        raise TokenError("Malformed verification token.")
    return uid


# --------------------------------------------------------------------------- #
# Password reset
# --------------------------------------------------------------------------- #
def _password_reset_fingerprint(user) -> str:
    """A short hash that changes when the password or last_login changes."""
    last_login = "" if user.last_login is None else user.last_login.isoformat()
    payload = f"{user.pk}:{user.password}:{last_login}"
    return hashlib.sha256(payload.encode()).hexdigest()[:20]


def generate_password_reset_token(user) -> str:
    return signing.dumps(
        {"uid": user.pk, "fp": _password_reset_fingerprint(user)},
        salt=PASSWORD_RESET_SALT,
    )


def read_password_reset_token(token: str):
    """Return the user for a valid, unused reset token, else raise TokenError."""
    try:
        data = signing.loads(
            token, salt=PASSWORD_RESET_SALT, max_age=settings.PASSWORD_RESET_TIMEOUT
        )
    except signing.BadSignature as exc:  # includes SignatureExpired
        raise TokenError("Invalid or expired reset token.") from exc

    uid = data.get("uid")
    fingerprint = data.get("fp", "")
    if uid is None:
        raise TokenError("Malformed reset token.")

    try:
        user = User.objects.get(pk=uid)
    except User.DoesNotExist as exc:
        raise TokenError("Invalid reset token.") from exc

    # Constant-time comparison; mismatch ⇒ token already used / state changed.
    if not hmac.compare_digest(_password_reset_fingerprint(user), fingerprint):
        raise TokenError("This reset token has already been used or has expired.")
    return user
