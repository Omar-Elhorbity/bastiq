"""Tests for IsOrganizationMember — the active-org resolution invariant.

A throwaway view guarded by the permission is mounted via a test-local
ROOT_URLCONF, then exercised through the real request pipeline so the header →
membership → request.organization resolution is tested end-to-end.
"""

from __future__ import annotations

import pytest
from django.urls import path
from rest_framework.response import Response
from rest_framework.views import APIView

from core.permissions import IsOrganizationMember
from organizations.tests.factories import MembershipFactory, OrganizationFactory


class _OrgEchoView(APIView):
    permission_classes = [IsOrganizationMember]

    def get(self, request):
        return Response({"org": request.organization.id, "role": request.membership.role})

    def post(self, request):
        # Echoes the resolved org so tests can prove the body never influences it.
        return Response({"org": request.organization.id, "role": request.membership.role})


urlpatterns = [path("_org-echo", _OrgEchoView.as_view())]

ECHO = "/_org-echo"
pytestmark = [pytest.mark.django_db, pytest.mark.urls(__name__)]


def test_member_resolves_active_org(as_user):
    membership = MembershipFactory()
    client = as_user(membership.user, org=membership.organization)
    resp = client.get(ECHO)
    assert resp.status_code == 200
    assert resp.json() == {"org": membership.organization.id, "role": membership.role}


def test_non_member_is_denied(as_user):
    membership = MembershipFactory()
    other_org = OrganizationFactory()
    # The user belongs to membership.organization, not other_org.
    client = as_user(membership.user, org=other_org)
    assert client.get(ECHO).status_code == 403


def test_missing_header_is_denied(as_user):
    membership = MembershipFactory()
    client = as_user(membership.user)  # no X-Organization-ID
    assert client.get(ECHO).status_code == 403


def test_non_integer_header_is_denied(as_user):
    membership = MembershipFactory()
    client = as_user(membership.user, org="not-an-int")
    assert client.get(ECHO).status_code == 403


def test_unauthenticated_is_denied(api_client):
    org = OrganizationFactory()
    api_client.credentials(HTTP_X_ORGANIZATION_ID=str(org.id))
    assert api_client.get(ECHO).status_code in (401, 403)


def test_org_is_never_taken_from_query_params(as_user):
    """A different org id in the query string is ignored; only the header counts."""
    membership = MembershipFactory()
    other_org = OrganizationFactory()
    client = as_user(membership.user, org=membership.organization)
    resp = client.get(ECHO, data={"organization": other_org.id})
    assert resp.status_code == 200
    assert resp.json()["org"] == membership.organization.id


def test_org_is_never_taken_from_request_body(as_user):
    """A POST body that names another org is ignored; only the header counts."""
    membership = MembershipFactory()
    other_org = OrganizationFactory()
    client = as_user(membership.user, org=membership.organization)
    resp = client.post(ECHO, data={"organization": other_org.id}, format="json")
    assert resp.status_code == 200
    assert resp.json()["org"] == membership.organization.id
