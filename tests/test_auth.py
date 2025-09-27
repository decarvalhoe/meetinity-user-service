import os
import pytest

os.environ.setdefault("JWT_SECRET", "testsecret")
os.environ.setdefault(
    "GOOGLE_REDIRECT_URI", "http://localhost/auth/google/callback"
)
os.environ.setdefault(
    "LINKEDIN_REDIRECT_URI", "http://localhost/auth/linkedin/callback"
)

from src.main import app  # noqa: E402
from src.models.user import (  # noqa: E402
    get_user_by_email,
    reset_storage,
    upsert_user,
)
from src.auth.oauth import generate_nonce, generate_state  # noqa: E402


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client
    reset_storage()


def mock_build_auth_url(provider, redirect_uri, state, nonce=None):
    return f"https://auth.example/{provider}?state={state}"  # noqa: E231


def mock_fetch_user_info(provider, code, redirect_uri, nonce=None):
    if provider == "google":
        return {
            "email": "test@example.com",
            "name": "Test User",
            "sub": "abc",
            "picture": "http://pic",
        }
    if provider == "linkedin":
        return {
            "email": "ln@example.com",
            "localizedFirstName": "Ln",
            "id": "ln123",
            "profilePicture": "http://pic-ln",
        }
    return {}


def test_google_flow(client, monkeypatch):
    monkeypatch.setattr("src.routes.auth.build_auth_url", mock_build_auth_url)
    monkeypatch.setattr(
        "src.routes.auth.fetch_user_info", mock_fetch_user_info
    )

    resp = client.post("/auth/google")
    assert resp.status_code == 200
    with client.session_transaction() as sess:
        state = sess["state"]
    resp = client.get(f"/auth/google/callback?code=abc&state={state}")
    assert resp.status_code == 200
    token = resp.json["token"]
    assert resp.json["user"]["email"] == "test@example.com"

    resp = client.post("/auth/verify", json={"token": token})
    assert resp.status_code == 200
    assert resp.json["valid"]

    resp = client.get(
        "/auth/profile", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200
    assert resp.json["user"]["email"] == "test@example.com"


def test_linkedin_flow(client, monkeypatch):
    monkeypatch.setattr("src.routes.auth.build_auth_url", mock_build_auth_url)
    monkeypatch.setattr(
        "src.routes.auth.fetch_user_info", mock_fetch_user_info
    )

    resp = client.post("/auth/linkedin")
    assert resp.status_code == 200
    with client.session_transaction() as sess:
        state = sess["state"]
    resp = client.get(
        f"/auth/linkedin/callback?code=code&state={state}"
    )
    assert resp.status_code == 200
    assert resp.json["user"]["email"] == "ln@example.com"


def test_google_flow_with_custom_redirect(client, monkeypatch):
    custom_redirect = "http://localhost/custom"
    captured = {}

    monkeypatch.setattr("src.routes.auth.build_auth_url", mock_build_auth_url)

    def capturing_fetch(provider, code, redirect_uri, nonce=None):
        captured["redirect_uri"] = redirect_uri
        return mock_fetch_user_info(provider, code, redirect_uri, nonce)

    monkeypatch.setattr("src.routes.auth.fetch_user_info", capturing_fetch)
    monkeypatch.setattr(
        "src.routes.auth.ALLOWED_REDIRECTS", {custom_redirect}
    )

    resp = client.post(
        "/auth/google", json={"redirect_uri": custom_redirect}
    )
    assert resp.status_code == 200
    with client.session_transaction() as sess:
        state = sess["state"]
        assert sess["redirect_uri"] == custom_redirect

    resp = client.get(f"/auth/google/callback?code=abc&state={state}")
    assert resp.status_code == 200
    assert captured["redirect_uri"] == custom_redirect

    with client.session_transaction() as sess:
        assert "state" not in sess
        assert "nonce" not in sess
        assert "redirect_uri" not in sess


def test_invalid_state(client, monkeypatch):
    monkeypatch.setattr("src.routes.auth.build_auth_url", mock_build_auth_url)
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


def test_profile_missing_token(client):
    resp = client.get("/auth/profile")
    assert resp.status_code == 401


def test_helpers_and_model():
    state1 = generate_state()
    nonce1 = generate_nonce()
    assert state1 and nonce1
    assert state1 != generate_state()
    user = upsert_user("a@example.com", name="A")
    user2 = upsert_user("a@example.com", name="B")
    assert user.id == user2.id
    assert get_user_by_email("a@example.com").name == "B"
