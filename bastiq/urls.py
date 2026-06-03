"""Root URL configuration.

API surface lives under ``/api/``. Each app owns its own urlconf and is included
here, keeping route ownership next to the code that implements it.
"""

from __future__ import annotations

from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
)

from core.views import healthz

# Admin branding.
admin.site.site_header = "Bastiq administration"
admin.site.site_title = "Bastiq admin"
admin.site.index_title = "Bastiq"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("healthz", healthz, name="healthz"),
    # OpenAPI schema + Swagger UI.
    path("api/schema", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/docs",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    # App routes (added per milestone).
    path("api/auth/", include("accounts.urls")),
    path("api/", include("organizations.urls")),
    path("api/billing/", include("billing.urls")),
    path("api/", include("projects.urls")),
]
