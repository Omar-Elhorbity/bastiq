"""Test factory for projects."""

from __future__ import annotations

import factory

from accounts.tests.factories import UserFactory
from organizations.tests.factories import OrganizationFactory
from projects.models import Project


class ProjectFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Project

    organization = factory.SubFactory(OrganizationFactory)
    name = factory.Sequence(lambda n: f"Project {n}")
    description = ""
    created_by = factory.SubFactory(UserFactory)
