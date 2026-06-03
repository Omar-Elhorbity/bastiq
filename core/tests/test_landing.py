"""Site root serves a public, GET-only landing page (not a 404)."""

from __future__ import annotations


def test_landing_ok_and_public(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response["Content-Type"].startswith("text/html")
    body = response.content.decode()
    assert "Bastiq" in body
    # Points visitors at the interactive docs.
    assert "/api/docs" in body


def test_landing_rejects_post(client):
    assert client.post("/").status_code == 405
