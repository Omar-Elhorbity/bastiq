"""Health probe is public, GET-only, and dependency-free."""

from __future__ import annotations


def test_healthz_ok(client):
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_healthz_requires_no_auth(client):
    # No Authorization header at all → still 200.
    assert client.get("/healthz").status_code == 200


def test_healthz_rejects_post(client):
    assert client.post("/healthz").status_code == 405
