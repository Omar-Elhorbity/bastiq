"""Organization invitation email."""

from __future__ import annotations

from urllib.parse import urlencode

from django.conf import settings
from django.core.mail import send_mail


def send_invitation_email(invitation) -> None:
    link = f"{settings.FRONTEND_URL}/invitations/accept?" + urlencode({"token": invitation.token})
    org_name = invitation.organization.name
    subject = f"You're invited to join {org_name} on Bastiq"
    body = (
        f"You've been invited to join {org_name} as a {invitation.get_role_display()}.\n\n"
        f"Accept by opening this link (you'll need a Bastiq account for {invitation.email}):\n"
        f"{link}\n\n"
        f"Or POST this token to /api/invitations/accept:\n{invitation.token}\n\n"
        f"This invitation expires on {invitation.expires_at:%Y-%m-%d %H:%M UTC}.\n"
    )
    send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [invitation.email])
