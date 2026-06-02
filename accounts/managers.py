"""Email-based user manager.

The default :class:`~django.contrib.auth.models.UserManager` is keyed on
``username``. Bastiq logs in with email, so we provide create_user /
create_superuser that take an email as the identifier and normalise it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import BaseUserManager

if TYPE_CHECKING:  # pragma: no cover
    from accounts.models import User


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email: str, password: str | None, **extra_fields) -> User:
        if not email:
            raise ValueError("An email address is required.")
        # normalize_email() only lower-cases the domain. Email is our login
        # identifier, so lower-case the whole address to make identity
        # unambiguously case-insensitive (and consistent with the DB-level
        # Lower(email) unique constraint on the model).
        email = self.normalize_email(email).lower()
        user = self.model(email=email, **extra_fields)
        # make_password(None) yields an unusable password (login disabled until set).
        user.password = make_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email: str, password: str | None = None, **extra_fields) -> User:
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email: str, password: str | None = None, **extra_fields) -> User:
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_email_verified", True)
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")
        return self._create_user(email, password, **extra_fields)
