"""Smoke tests for the Flask application."""

from datetime import datetime


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "ok"
    timestamp = datetime.fromisoformat(data["timestamp"])
    assert timestamp.tzinfo is not None


def test_users_endpoint(client):
    response = client.get("/users")
    assert response.status_code == 200
    assert response.get_json() == {"users": []}


def test_not_found(client):
    response = client.get("/missing")
    assert response.status_code == 404
    payload = response.get_json()
    assert payload["error"]


def test_cors_headers(client):
    response = client.get("/health")
    assert response.headers["Access-Control-Allow-Origin"] == "*"
