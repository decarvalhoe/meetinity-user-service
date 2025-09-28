"""Tests for the authentication routes and repository."""

import os
from datetime import datetime, timedelta, timezone

import pytest

from src.auth.oauth import generate_nonce, generate_state
from src.db.session import session_scope
from src.models.user_repository import UserRepository


class DummyResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload

    def raise_for_status(self):
        if not 200 <= self.status_code < 300:
            raise RuntimeError(f"HTTP {self.status_code}")


class DummyLinkedInClient:
    def __init__(self, profile_payload, email_payload):
        self.profile_payload = profile_payload
        self.email_payload = email_payload
        self.fetch_token_calls = []
        self.get_calls = []

    def fetch_token(self, code, redirect_uri):
        self.fetch_token_calls.append((code, redirect_uri))
        return {"access_token": "dummy-token"}

    def get(self, endpoint, token=None, params=None):
        self.get_calls.append((endpoint, token, params))
        if endpoint == "me":
            return DummyResponse(self.profile_payload)
        if endpoint == "emailAddress":
            return DummyResponse(self.email_payload)
        raise AssertionError(f"Unexpected endpoint {endpoint}")


def mock_build_auth_url(provider, redirect_uri, state, nonce=None):
    """Return a deterministic authorization URL for tests."""

    return "https://auth.example/" + provider + "?state=" + state


def mock_fetch_user_info(provider, code, redirect_uri, nonce=None):
    if provider == "google":
        return {
            "email": "test@example.com",
            "name": "Test User",
            "sub": "abc",
            "picture": "http://pic",
        }
    raise AssertionError("unexpected provider")


@pytest.fixture
def stubbed_google(monkeypatch):
    monkeypatch.setattr(
        "src.routes.auth.build_auth_url",
        mock_build_auth_url,
    )
    monkeypatch.setattr(
        "src.routes.auth.fetch_user_info",
        mock_fetch_user_info,
    )


def test_google_flow(client, stubbed_google):
    resp = client.post("/auth/google")
    assert resp.status_code == 200
    with client.session_transaction() as sess:
        state = sess["state"]

    resp = client.get(f"/auth/google/callback?code=abc&state={state}")
    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["user"]["email"] == "test@example.com"
    token = payload["token"]

    verify = client.post("/auth/verify", json={"token": token})
    assert verify.status_code == 200

    with session_scope() as session:
        repo = UserRepository(session)
        stored = repo.get_by_email("test@example.com")
        assert stored is not None
        assert stored.login_count == 1


def test_linkedin_flow(client, monkeypatch):
    monkeypatch.setattr("src.routes.auth.build_auth_url", mock_build_auth_url)

    profile_payload = {
        "id": "ln123",
        "localizedFirstName": "Ln",
        "localizedLastName": "User",
        "profilePicture": {
            "displayImage~": {
                "elements": [
                    {"identifiers": [{"identifier": "http://pic-ln"}]}
                ]
            }
        },
    }
    email_payload = {
        "elements": [
            {"handle~": {"emailAddress": "ln@example.com"}},
        ]
    }
    dummy_client = DummyLinkedInClient(profile_payload, email_payload)

    def fake_create_client(name):
        assert name == "linkedin"
        return dummy_client

    monkeypatch.setattr(
        "src.auth.oauth.oauth.create_client",
        fake_create_client,
    )

    resp = client.post("/auth/linkedin")
    assert resp.status_code == 200
    with client.session_transaction() as sess:
        state = sess["state"]

    callback_url = f"/auth/linkedin/callback?code=code&state={state}"
    resp = client.get(callback_url)
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["user"]["email"] == "ln@example.com"
    assert body["user"]["name"] == "Ln User"

    with session_scope() as session:
        repo = UserRepository(session)
        user = repo.get_by_email("ln@example.com")
        assert user.provider == "linkedin"
        assert user.social_accounts[0].provider_user_id == "ln123"
        assert user.social_accounts[0].profile_url == "http://pic-ln"

    assert dummy_client.fetch_token_calls == [
        ("code", os.getenv("LINKEDIN_REDIRECT_URI"))
    ]
    endpoints = [call[0] for call in dummy_client.get_calls]
    assert endpoints == ["me", "emailAddress"]


def test_google_flow_with_custom_redirect(client, monkeypatch, stubbed_google):
    custom_redirect = "http://localhost/custom"
    monkeypatch.setattr("src.routes.auth.ALLOWED_REDIRECTS", {custom_redirect})

    resp = client.post("/auth/google", json={"redirect_uri": custom_redirect})
    assert resp.status_code == 200
    with client.session_transaction() as sess:
        state = sess["state"]
        assert sess["redirect_uri"] == custom_redirect

    resp = client.get(f"/auth/google/callback?code=abc&state={state}")
    assert resp.status_code == 200


def test_invalid_state(client, stubbed_google):
    resp = client.post("/auth/google")
    assert resp.status_code == 200
    resp = client.get("/auth/google/callback?code=abc&state=wrong")
    assert resp.status_code == 401


def test_invalid_redirect(client):
    resp = client.post(
        "/auth/google",
        json={"redirect_uri": "http://evil.com/callback"},
    )
    assert resp.status_code == 400


def test_verify_invalid_token(client):
    resp = client.post("/auth/verify", json={"token": "bad"})
    assert resp.status_code == 401


def test_profile_requires_token(client):
    resp = client.get("/auth/profile")
    assert resp.status_code == 401


def test_profile_caching(monkeypatch, client):
    class FakeRedis:
        def __init__(self):
            self.data: dict[str, str] = {}

        def get(self, key):
            return self.data.get(key)

        def setex(self, key, ttl, value):
            self.data[key] = value

        def delete(self, key):
            self.data.pop(key, None)

    fake_redis = FakeRedis()
    client.application.extensions["redis_client"] = fake_redis

    with session_scope() as session:
        repo = UserRepository(session)
        user = repo.upsert_oauth_user(
            email="cache@example.com",
            provider="google",
            name="Cache User",
            provider_user_id="cache-id",
            last_login=datetime.now(timezone.utc),
        )
        user_id = user.id

    token_payload = {"sub": user_id, "email": "cache@example.com"}
    monkeypatch.setattr(
        "src.auth.jwt_handler.decode_jwt",
        lambda token: token_payload,
    )

    first = client.get(
        "/auth/profile",
        headers={"Authorization": "Bearer dummy"},
    )
    assert first.status_code == 200
    assert fake_redis.data

    def _raise_get(self, user_id):  # pragma: no cover - should not run
        raise AssertionError("repository should not be queried when cached")

    monkeypatch.setattr("src.routes.auth.UserRepository.get", _raise_get)

    second = client.get(
        "/auth/profile",
        headers={"Authorization": "Bearer dummy"},
    )
    assert second.status_code == 200
    client.application.extensions.pop("redis_client", None)


def test_repository_helpers():
    state1 = generate_state()
    nonce1 = generate_nonce()
    assert state1 and nonce1 and state1 != generate_state()

    now = datetime.now(timezone.utc)
    with session_scope() as session:
        repo = UserRepository(session)
        user = repo.upsert_oauth_user(
            email="helper@example.com",
            provider="google",
            name="Helper",
            provider_user_id="help",
            last_login=now,
        )
        repo.set_preferences(user, {"newsletter": "1", "theme": "dark"})
        repo.deactivate(user)

    with session_scope() as session:
        repo = UserRepository(session)
        stored = repo.get_by_email("helper@example.com")
        assert stored is not None
        assert stored.preferences[0].key in {"newsletter", "theme"}
        assert not stored.is_active


def test_verification_request_and_confirm(client):
    with session_scope() as session:
        repo = UserRepository(session)
        user = repo.create_user(email="verify@example.com")
        user_id = user.id

    expires_at = (
        datetime.now(timezone.utc) + timedelta(minutes=5)
    ).isoformat()
    request_resp = client.post(
        "/auth/verification/request",
        json={
            "user_id": user_id,
            "method": "email",
            "code": "123456",
            "expires_at": expires_at,
        },
    )
    assert request_resp.status_code == 201
    verification_id = request_resp.get_json()["verification"]["id"]

    confirm_resp = client.post(
        "/auth/verification/confirm",
        json={"verification_id": verification_id, "code": "123456"},
    )
    assert confirm_resp.status_code == 200
    payload = confirm_resp.get_json()
    assert payload["success"] is True
    assert payload["verification"]["status"] == "verified"


def test_verification_rejects_wrong_code(client):
    with session_scope() as session:
        repo = UserRepository(session)
        user = repo.create_user(email="wrong@example.com")
        user_id = user.id

    request_resp = client.post(
        "/auth/verification/request",
        json={"user_id": user_id, "method": "email", "code": "222"},
    )
    assert request_resp.status_code == 201
    verification_id = request_resp.get_json()["verification"]["id"]

    confirm_resp = client.post(
        "/auth/verification/confirm",
        json={"verification_id": verification_id, "code": "999"},
    )
    assert confirm_resp.status_code == 422
    payload = confirm_resp.get_json()
    assert payload["success"] is False
