"""Organization routes, mounted under /api/ by the root urlconf."""

from __future__ import annotations

from rest_framework.routers import SimpleRouter

from organizations.views import OrganizationViewSet

app_name = "organizations"

# SimpleRouter (no API-root view) so multiple app routers can share /api/.
router = SimpleRouter(trailing_slash=False)
router.register("organizations", OrganizationViewSet, basename="organization")

urlpatterns = router.urls
