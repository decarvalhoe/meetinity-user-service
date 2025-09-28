"""Smoke tests for the Flask application."""

from datetime import datetime

from src.config import reset_config
from src.main import create_app


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


def test_custom_cors_origin_allowed():
    reset_config({"CORS_ORIGINS": "https://allowed.example"})
    try:
        app = create_app()
        app.config.update({"TESTING": True})
        with app.test_client() as client:
            response = client.get(
                "/health", headers={"Origin": "https://allowed.example"}
            )
            assert (
                response.headers["Access-Control-Allow-Origin"]
                == "https://allowed.example"
            )
    finally:
        reset_config({"CORS_ORIGINS": None})


def test_custom_cors_origin_rejected():
    reset_config({"CORS_ORIGINS": "https://allowed.example"})
    try:
        app = create_app()
        app.config.update({"TESTING": True})
        with app.test_client() as client:
            response = client.get(
                "/health", headers={"Origin": "https://other.example"}
            )
            assert "Access-Control-Allow-Origin" not in response.headers
    finally:
        reset_config({"CORS_ORIGINS": None})
