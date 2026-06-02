"""Tenancy base classes.

Every tenant-owned model inherits :class:`TenantScopedModel` (giving it an
``organization`` FK), and every tenant-owned API inherits
:class:`core.viewsets.TenantScopedViewSet`. Together they guarantee the
isolation invariant: a tenant queryset is never evaluated without an
``organization`` filter, and the org is taken only from the validated active-org
(``request.organization``) — never from client input.
"""

from __future__ import annotations

from django.db import models


class TenantQuerySet(models.QuerySet):
    def for_org(self, org) -> TenantQuerySet:
        return self.filter(organization=org)


class TenantManager(models.Manager.from_queryset(TenantQuerySet)):
    pass


class TenantScopedModel(models.Model):
    # related_name expands per concrete model: Project → organization.projects.
    # CONSTRAINT: two concrete tenant models with the *same class name* (in
    # different apps) would clash on this reverse accessor. We own every tenant
    # model, so we keep names unique; a same-named model must set its own
    # related_name (or we'd switch this to "%(app_label)s_%(class)ss").
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="%(class)ss",
    )

    objects = TenantManager()

    class Meta:
        abstract = True
