from datetime import datetime
import os
import sys

import pytest

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
)
from src.main import create_app  # noqa: E402


@pytest.fixture
def client():
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "ok"
    ts = datetime.fromisoformat(data["timestamp"].replace("Z", "+00:00"))
    assert ts.tzinfo is not None


def test_users(client):
    response = client.get("/users")
    assert response.status_code == 200
    assert "users" in response.get_json()


def test_not_found(client):
    response = client.get("/missing")
    assert response.status_code == 404
    assert "error" in response.get_json()


def test_cors_headers(client):
    response = client.get("/health")
    assert response.headers["Access-Control-Allow-Origin"] == "*"
