"""Celery tasks for async auth emails.

Tasks take a user id (not a token) so nothing sensitive sits in the broker; the
token is minted inside the task at send time.
"""

from __future__ import annotations

from celery import shared_task
from django.contrib.auth import get_user_model

from accounts import emails


@shared_task(ignore_result=True)
def send_verification_email_task(user_id: int) -> None:
    User = get_user_model()
    user = User.objects.filter(pk=user_id).first()
    if user is not None:
        emails.send_verification_email(user)


@shared_task(ignore_result=True)
def send_password_reset_email_task(user_id: int) -> None:
    User = get_user_model()
    user = User.objects.filter(pk=user_id).first()
    if user is not None:
        emails.send_password_reset_email(user)
