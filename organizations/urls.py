"""Organization & invitation routes, mounted under /api/ by the root urlconf."""

from __future__ import annotations

from django.urls import path
from rest_framework.routers import SimpleRouter

from organizations.views import InvitationAcceptView, OrganizationViewSet

app_name = "organizations"

# SimpleRouter (no API-root view) so multiple app routers can share /api/.
router = SimpleRouter(trailing_slash=False)
router.register("organizations", OrganizationViewSet, basename="organization")

urlpatterns = [
    path("invitations/accept", InvitationAcceptView.as_view(), name="invitation-accept"),
    *router.urls,
]
