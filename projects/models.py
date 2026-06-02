"""Project — the sample tenant-scoped resource.

Inherits ``organization`` from ``TenantScopedModel``; isolation, RBAC (M4), and
plan limits (M5) are demonstrated end-to-end on this model.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models

from core.models import TenantScopedModel


class Project(TenantScopedModel):
    # Names are not unique within an org — duplicates are intentionally allowed
    # (no business requirement otherwise; e.g. re-creating after deletion).
    name = models.CharField(max_length=255)
    # Bounded so the API can't be used to store unbounded payloads. (Postgres
    # TEXT has no length limit; max_length makes DRF reject over-long input.)
    description = models.TextField(blank=True, max_length=5000)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.name
