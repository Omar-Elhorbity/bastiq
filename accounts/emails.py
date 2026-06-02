"""Transactional auth emails (verification & password reset).

Content building + sending live here (synchronous); ``tasks.py`` wraps these in
Celery tasks. The body includes both a link and the raw token so the demo can
copy the token straight into Swagger (emails go to the console in dev).
"""

from __future__ import annotations

from urllib.parse import urlencode

from django.conf import settings
from django.core.mail import send_mail

from accounts.tokens import (
    generate_email_verification_token,
    generate_password_reset_token,
)


def _link(path: str, token: str) -> str:
    return f"{settings.FRONTEND_URL}{path}?{urlencode({'token': token})}"


def send_verification_email(user) -> None:
    token = generate_email_verification_token(user)
    link = _link("/verify-email", token)
    hours = settings.EMAIL_VERIFICATION_TIMEOUT // 3600
    subject = "Verify your Bastiq email address"
    body = (
        f"Hi {user.full_name},\n\n"
        f"Confirm your email address by opening this link:\n{link}\n\n"
        f"Or POST this token to /api/auth/verify-email:\n{token}\n\n"
        f"This link expires in {hours} hours. If you didn't sign up, ignore this email.\n"
    )
    send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [user.email])


def send_password_reset_email(user) -> None:
    token = generate_password_reset_token(user)
    link = _link("/reset-password", token)
    minutes = settings.PASSWORD_RESET_TIMEOUT // 60
    subject = "Reset your Bastiq password"
    body = (
        f"Hi {user.full_name},\n\n"
        f"Reset your password by opening this link:\n{link}\n\n"
        f"Or POST this token with a new password to /api/auth/password-reset/confirm:\n{token}\n\n"
        f"This link expires in {minutes} minutes. If you didn't request this, ignore this email.\n"
    )
    send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [user.email])
