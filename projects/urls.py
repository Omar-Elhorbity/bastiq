"""Project routes, mounted under /api/ by the root urlconf."""

from __future__ import annotations

from rest_framework.routers import SimpleRouter

from projects.views import ProjectViewSet

app_name = "projects"

router = SimpleRouter(trailing_slash=False)
router.register("projects", ProjectViewSet, basename="project")

urlpatterns = router.urls
