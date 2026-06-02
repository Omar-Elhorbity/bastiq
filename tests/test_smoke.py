"""M0 smoke tests: the app boots, JWT auth resolves a user, docs are served."""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIRequestFactory
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.tokens import RefreshToken

pytestmark = pytest.mark.django_db

User = get_user_model()


def test_jwt_authenticates_request_to_a_user():
    """The M0 'done' criterion: an authed request resolves to a user."""
    user = User.objects.create_user(email="alice@example.com", password="pw-123456789")
    access = RefreshToken.for_user(user).access_token

    request = APIRequestFactory().get("/", HTTP_AUTHORIZATION=f"Bearer {access}")
    resolved_user, validated_token = JWTAuthentication().authenticate(request)

    assert resolved_user == user
    assert validated_token["user_id"] == str(user.id) or validated_token["user_id"] == user.id


def test_bad_token_is_rejected():
    request = APIRequestFactory().get("/", HTTP_AUTHORIZATION="Bearer not-a-real-token")
    from rest_framework.exceptions import AuthenticationFailed

    with pytest.raises(AuthenticationFailed):
        JWTAuthentication().authenticate(request)


def test_openapi_schema_is_served(client):
    response = client.get("/api/schema")
    assert response.status_code == 200
    body = response.content.decode()
    assert "openapi" in body


def test_swagger_docs_are_served(client):
    response = client.get("/api/docs")
    assert response.status_code == 200


def test_docs_serve_permissions_default_public(settings):
    """Docs are public by default (the demo needs a reachable Swagger).

    The lever is DOCS_REQUIRE_AUTH (read at startup → SERVE_PERMISSIONS); it is
    bound to the view class at import, so it is a deploy-time setting rather
    than a runtime toggle. Here we assert the default wiring is public.
    """
    assert settings.SPECTACULAR_SETTINGS["SERVE_PERMISSIONS"] == [
        "rest_framework.permissions.AllowAny"
    ]
