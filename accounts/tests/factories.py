"""Test factories for accounts."""

from __future__ import annotations

import factory
from django.contrib.auth import get_user_model

User = get_user_model()


class UserFactory(factory.django.DjangoModelFactory):
    """Creates users through the real manager.

    Routing through ``create_user`` (rather than DjangoModelFactory's default
    ``Model.objects.create``) keeps tests faithful to production: email is
    normalised/lower-cased and the password is hashed the same way.
    """

    class Meta:
        model = User

    email = factory.Sequence(lambda n: f"user{n}@example.com")
    first_name = factory.Faker("first_name")
    last_name = factory.Faker("last_name")
    is_email_verified = True

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        password = kwargs.pop("password", "sup3r-secret-pw")
        manager = cls._get_manager(model_class)
        return manager.create_user(*args, password=password, **kwargs)
