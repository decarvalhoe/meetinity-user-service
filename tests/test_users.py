"""Tests for the user profile endpoints."""

from __future__ import annotations

import io
import os
import tempfile

import pytest

from src.db.session import session_scope
from src.models.user_repository import UserRepository
from src.routes.auth import _profile_cache_key


class DummyRedis:
    """Minimal Redis-like interface for testing cache invalidation."""

    def __init__(self):
        self.store: dict[str, object] = {}

    def get(self, key: str):
        return self.store.get(key)

    def setex(self, key: str, ttl: int, value: object):
        self.store[key] = value

    def delete(self, key: str):
        self.store.pop(key, None)


@pytest.fixture
def seeded_users():
    with session_scope() as session:
        repo = UserRepository(session)
        alice = repo.create_user(
            email="alice@example.com",
            name="Alice",
            industry="Technology",
            location="Paris",
            experience_years=5,
            title="Platform Engineer",
            skills=["python", "flask"],
            interests=["networking"],
        )
        bob = repo.create_user(
            email="bob@example.com",
            name="Bob",
            industry="Finance",
            location="London",
            experience_years=8,
            skills=["excel", "python"],
        )
        carol = repo.create_user(
            email="carol@example.com",
            name="Carol",
            industry="Technology",
            location="Paris",
            experience_years=2,
            skills=["javascript"],
            bio="Enthusiastic engineer",
        )
        yield {"alice": alice, "bob": bob, "carol": carol}


def test_list_users_with_filters(client, seeded_users):
    response = client.get(
        "/users",
        query_string={
            "industry": "Technology",
            "location": "Paris",
            "skills": "python",
            "sort": "experience_years:desc",
        },
    )
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["total"] == 1
    assert payload["items"][0]["email"] == "alice@example.com"
    assert payload["items"][0]["skills"] == ["python", "flask"]


def test_get_user_returns_profile(client, seeded_users):
    alice_id = seeded_users["alice"].id
    response = client.get(f"/users/{alice_id}")
    assert response.status_code == 200
    body = response.get_json()
    assert body["user"]["name"] == "Alice"
    assert body["user"]["industry"] == "Technology"


def test_update_user(client, seeded_users):
    alice_id = seeded_users["alice"].id
    response = client.put(
        f"/users/{alice_id}",
        json={
            "title": "Senior Engineer",
            "skills": ["Python", "Flask", "SQLAlchemy"],
            "linkedin_url": "https://linkedin.com/in/alice",
        },
    )
    assert response.status_code == 200
    updated = response.get_json()["user"]
    assert updated["title"] == "Senior Engineer"
    assert "sqlalchemy" in updated["skills"]

    with session_scope() as session:
        repo = UserRepository(session)
        stored = repo.get(alice_id)
        assert stored.title == "Senior Engineer"
        assert stored.linkedin_url == "https://linkedin.com/in/alice"


def test_update_user_clears_cached_profile(client, seeded_users):
    alice_id = seeded_users["alice"].id
    fake_cache = DummyRedis()
    app = client.application
    previous_cache = app.extensions.get("redis_client")
    app.extensions["redis_client"] = fake_cache
    cache_key = _profile_cache_key(alice_id)
    fake_cache.setex(cache_key, 60, {"name": "Old Alice"})

    try:
        response = client.put(
            f"/users/{alice_id}",
            json={"title": "Principal Engineer"},
        )
        assert response.status_code == 200
        assert cache_key not in fake_cache.store
    finally:
        if previous_cache is not None:
            app.extensions["redis_client"] = previous_cache
        else:
            app.extensions.pop("redis_client", None)


def test_delete_user(client, seeded_users):
    bob_id = seeded_users["bob"].id
    response = client.delete(f"/users/{bob_id}")
    assert response.status_code == 204

    with session_scope() as session:
        repo = UserRepository(session)
        assert repo.get(bob_id) is None


def test_upload_photo(client, seeded_users, tmp_path):
    user_id = seeded_users["carol"].id
    temp_dir = tempfile.mkdtemp(dir=tmp_path)
    client.application.config["UPLOAD_FOLDER"] = temp_dir
    client.application.config["UPLOAD_URL_PREFIX"] = "/media"

    image_data = io.BytesIO(b"\x89PNG\r\n\x1a\n" + b"0" * 16)
    image_data.name = "avatar.png"

    response = client.post(
        f"/users/{user_id}/photo",
        data={"photo": (image_data, "avatar.png")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 201
    payload = response.get_json()
    assert payload["user_id"] == user_id
    assert payload["photo_url"].startswith("/media/")

    stored_file = os.path.join(
        temp_dir,
        os.path.basename(payload["photo_url"]),
    )
    assert os.path.exists(stored_file)


def test_search_users(client, seeded_users):
    response = client.get("/users/search", query_string={"q": "engineer"})
    assert response.status_code == 200
    data = response.get_json()
    emails = {item["email"] for item in data["items"]}
    assert "carol@example.com" in emails
    assert "alice@example.com" in emails
