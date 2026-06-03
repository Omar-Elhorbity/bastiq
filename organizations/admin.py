"""Admin for organizations & memberships (richer org-scoped admin lands in M6)."""

from __future__ import annotations

from django.contrib import admin

from organizations.models import Invitation, Membership, Organization


class MembershipInline(admin.TabularInline):
    model = Membership
    extra = 0
    autocomplete_fields = ("user",)
    readonly_fields = ("created_at",)


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "created_by", "created_at")
    search_fields = ("name", "slug")
    readonly_fields = ("slug", "created_at")
    inlines = (MembershipInline,)


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ("user", "organization", "role", "created_at")
    list_filter = ("role",)
    search_fields = ("user__email", "organization__name")
    autocomplete_fields = ("user", "organization")
    readonly_fields = ("created_at",)


@admin.register(Invitation)
class InvitationAdmin(admin.ModelAdmin):
    list_display = ("email", "organization", "role", "status", "invited_by", "expires_at")
    list_filter = ("status", "role")
    search_fields = ("email", "organization__name")
    autocomplete_fields = ("organization", "invited_by")
    # token + expiry are system-set at creation; don't allow manual edits.
    readonly_fields = ("token", "created_at", "expires_at")
