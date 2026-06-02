"""Custom user model.

Email is the login identifier (no username). ``is_email_verified`` gates access
to email-confirmed flows; verification itself is built in M1 using signed,
expiring tokens (no token table). ``AUTH_USER_MODEL`` points here and is set
before the first migration — changing it later is extremely painful.
"""

from __future__ import annotations

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models.functions import Lower

from accounts.managers import UserManager


class User(AbstractUser):
    # Drop the username field entirely; email is the identifier.
    username = None  # type: ignore[assignment]

    email = models.EmailField("email address", unique=True)
    is_email_verified = models.BooleanField(
        default=False,
        help_text="Set once the user confirms ownership of their email address.",
    )

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: list[str] = []

    objects = UserManager()

    class Meta:
        verbose_name = "user"
        verbose_name_plural = "users"
        ordering = ["email"]
        constraints = [
            # DB-level case-insensitive uniqueness, independent of the
            # application's normalisation path (defends against raw inserts /
            # any code that skips the manager).
            models.UniqueConstraint(Lower("email"), name="user_email_ci_unique"),
        ]

    def __str__(self) -> str:
        return self.email

    @property
    def full_name(self) -> str:
        return self.get_full_name() or self.email
