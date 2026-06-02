"""Test factories for organizations & memberships."""

from __future__ import annotations

import factory

from accounts.tests.factories import UserFactory
from organizations.models import Membership, Organization, Role


class OrganizationFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Organization

    name = factory.Sequence(lambda n: f"Org {n}")
    slug = factory.Sequence(lambda n: f"org-{n}")
    created_by = factory.SubFactory(UserFactory)


class MembershipFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Membership

    user = factory.SubFactory(UserFactory)
    organization = factory.SubFactory(OrganizationFactory)
    role = Role.MEMBER
