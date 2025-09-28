# -*- coding: utf-8 -*-
"""Authentication routes for the User Service."""

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict

from flask import Blueprint, current_app, jsonify, request, session

from src.auth.jwt_handler import decode_jwt, encode_jwt, require_auth
from src.auth.oauth import (
    build_auth_url,
    fetch_user_info,
    generate_nonce,
    generate_state,
)
from src.db.session import session_scope
from src.models.user_repository import UserRepository
from src.schemas.user import UserSchema

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")
user_schema = UserSchema()

ALLOWED_REDIRECTS = {
    value.strip()
    for value in os.getenv("ALLOWED_REDIRECTS", "").split(",")
    if value.strip()
}


def _error(code: int, message: str, details: dict | None = None):
    """Create a standardized error response.

    Args:
        code (int): The HTTP status code.
        message (str): The error message.
        details (dict, optional): Additional error details. Defaults to None.

    Returns:
        Response: A JSON response with the error details.
    """
    return (
        jsonify(
            {
                "error": {
                    "code": code,
                    "message": message,
                    "details": details or {},
                }
            }
        ),
        code,
    )


@auth_bp.post("/<provider>")
def auth_start(provider: str):
    """Start the OAuth authentication process.

    Args:
        provider (str): The OAuth provider (e.g., 'google', 'linkedin').

    Returns:
        Response: A JSON response with the authentication URL.
    """
    if provider not in {"google", "linkedin"}:
        return _error(400, "bad provider")
    data = request.get_json(silent=True) or {}
    default_redirect_uri = os.getenv(f"{provider.upper()}_REDIRECT_URI")
    requested_redirect = data.get("redirect_uri")
    redirect_uri = requested_redirect or default_redirect_uri
    if requested_redirect:
        if (
            requested_redirect not in ALLOWED_REDIRECTS
            and requested_redirect != default_redirect_uri
        ):
            return _error(400, "invalid redirect")
        session["redirect_uri"] = requested_redirect
    else:
        session.pop("redirect_uri", None)
    state = generate_state()
    session["state"] = state
    nonce = generate_nonce() if provider == "google" else None
    if nonce:
        session["nonce"] = nonce
    url = build_auth_url(provider, redirect_uri, state, nonce)
    return jsonify({"auth_url": url})


@auth_bp.get("/<provider>/callback")
def auth_callback(provider: str):
    """Handle the OAuth callback.

    Args:
        provider (str): The OAuth provider.

    Returns:
        Response: A JSON response with the JWT and user information.
    """
    if provider not in {"google", "linkedin"}:
        return _error(400, "bad provider")
    try:
        code = request.args.get("code")
        state = request.args.get("state")
        if not code or not state:
            return _error(400, "missing code or state")
        if state != session.get("state"):
            return _error(401, "invalid state")
        nonce = session.get("nonce")
        redirect_uri = session.get("redirect_uri") or os.getenv(
            f"{provider.upper()}_REDIRECT_URI"
        )
        try:
            info = fetch_user_info(provider, code, redirect_uri, nonce)
        except Exception as exc:  # pragma: no cover - network failures
            return _error(401, "oauth error", {"reason": str(exc)})
        email = info.get("email")
        if not email:
            return _error(422, "email required")
        now = datetime.now(timezone.utc)
        redis_client = current_app.extensions.get("redis_client")
        try:
            with session_scope() as db_session:
                repo = UserRepository(db_session)
                user = repo.upsert_oauth_user(
                    email=email,
                    provider=provider,
                    provider_user_id=info.get("sub") or info.get("id"),
                    name=info.get("name")
                    or info.get("localizedFirstName"),
                    photo_url=info.get("picture")
                    or info.get("profilePicture"),
                    company=info.get("company"),
                    title=info.get("title"),
                    location=info.get("locale") or info.get("location"),
                    last_login=now,
                    social_profile_url=(
                        info.get("profile") or info.get("profilePicture")
                    ),
                )
                profile = _serialize_user(user)
        except ValueError as exc:
            return _error(422, str(exc))
        if redis_client:
            redis_client.setex(
                _profile_cache_key(user.id),
                current_app.config["APP_CONFIG"].redis_cache_ttl,
                json.dumps(profile),
            )
        token = encode_jwt(user)
        return jsonify({"token": token, "user": profile})
    finally:
        session.pop("state", None)
        session.pop("nonce", None)
        session.pop("redirect_uri", None)


@auth_bp.post("/verify")
def verify():
    """Verify a JWT.

    Returns:
        Response: A JSON response with the verification status.
    """
    data = request.get_json() or {}
    token = data.get("token")
    if not token:
        return _error(400, "missing token")
    try:
        payload = decode_jwt(token)
    except Exception as exc:  # pragma: no cover - jwt errors
        return _error(401, str(exc))
    return jsonify(
        {"valid": True, "sub": payload["sub"], "exp": payload["exp"]}
    )


@auth_bp.get("/profile")
@require_auth
def profile():
    """Get the user profile.

    Returns:
        Response: A JSON response with the user's profile information.
    """
    user_id = request.user["sub"]
    redis_client = current_app.extensions.get("redis_client")
    cache_key = _profile_cache_key(user_id)
    if redis_client:
        cached = redis_client.get(cache_key)
        if cached:
            return jsonify({"user": json.loads(cached)})

    with session_scope() as db_session:
        repo = UserRepository(db_session)
        user = repo.get(user_id)
        if not user:
            return _error(404, "user not found")
        profile = _serialize_user(user)

    if redis_client:
        redis_client.setex(
            cache_key,
            current_app.config["APP_CONFIG"].redis_cache_ttl,
            json.dumps(profile),
        )

    return jsonify({"user": profile})


def _profile_cache_key(user_id: int) -> str:
    return "user:profile:" + str(user_id)


def _serialize_user(user) -> Dict[str, Any]:
    """Serialize a user object for JSON responses/caching."""

    return user_schema.dump(user)
