"""The custom user model is the M0 linchpin — verify its contract."""

from __future__ import annotations

import pytest
from django.conf import settings
from django.contrib.auth import get_user_model

from accounts.tests.factories import UserFactory

pytestmark = pytest.mark.django_db

User = get_user_model()


def test_auth_user_model_is_accounts_user():
    assert settings.AUTH_USER_MODEL == "accounts.User"
    assert User._meta.label == "accounts.User"


def test_email_is_the_username_field():
    assert User.USERNAME_FIELD == "email"
    assert User.REQUIRED_FIELDS == []
    # username was removed from the model entirely.
    assert not hasattr(User(), "username") or User().username is None


def test_create_user_defaults():
    user = User.objects.create_user(email="Person@Example.com", password="pw-123456789")
    # The whole address is lower-cased — email is the login identifier.
    assert user.email == "person@example.com"
    assert user.check_password("pw-123456789")
    assert user.is_email_verified is False
    assert user.is_staff is False
    assert user.is_superuser is False
    assert user.is_active is True


def test_email_is_fully_lowercased():
    user = User.objects.create_user(email="MixedCase@Example.COM", password="pw-123456789")
    assert user.email == "mixedcase@example.com"


def test_email_uniqueness_is_case_insensitive():
    from django.db import IntegrityError

    User.objects.create_user(email="bob@example.com", password="pw-123456789")
    # Differs only by case → rejected by the Lower(email) unique constraint
    # (here, also by exact match since we store lower-cased).
    with pytest.raises(IntegrityError):
        User.objects.create_user(email="BOB@example.com", password="pw-123456789")


def test_factory_normalizes_email_like_production():
    # The factory must route through create_user, not raw create.
    user = UserFactory(email="Upper@Example.COM")
    assert user.email == "upper@example.com"


def test_create_user_requires_email():
    with pytest.raises(ValueError):
        User.objects.create_user(email="", password="pw-123456789")


def test_create_superuser():
    admin = User.objects.create_superuser(email="root@example.com", password="pw-123456789")
    assert admin.is_staff is True
    assert admin.is_superuser is True
    # Superusers are considered email-verified.
    assert admin.is_email_verified is True


def test_create_superuser_rejects_non_staff():
    with pytest.raises(ValueError):
        User.objects.create_superuser(
            email="root@example.com", password="pw-123456789", is_staff=False
        )


def test_email_uniqueness_enforced():
    from django.db import IntegrityError

    UserFactory(email="dup@example.com")
    with pytest.raises(IntegrityError):
        UserFactory(email="dup@example.com")


def test_str_and_full_name():
    user = UserFactory(email="jane@example.com", first_name="Jane", last_name="Doe")
    assert str(user) == "jane@example.com"
    assert user.full_name == "Jane Doe"
