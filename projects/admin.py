"""Admin for projects (org-scoped admin refinements land in M6)."""

from __future__ import annotations

from django.contrib import admin

from projects.models import Project


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("name", "organization", "created_by", "created_at")
    list_filter = ("organization",)
    search_fields = ("name", "description", "organization__name")
    autocomplete_fields = ("organization", "created_by")
    readonly_fields = ("created_at",)
