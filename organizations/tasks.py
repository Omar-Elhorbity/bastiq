"""Celery tasks for organization emails."""

from __future__ import annotations

from celery import shared_task

from organizations import emails
from organizations.models import Invitation


@shared_task(ignore_result=True)
def send_invitation_email_task(invitation_id: int) -> None:
    invitation = Invitation.objects.select_related("organization").filter(pk=invitation_id).first()
    if invitation is not None:
        emails.send_invitation_email(invitation)
