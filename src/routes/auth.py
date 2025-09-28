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
from src.routes.helpers import error_response
from src.schemas.user import UserSchema, UserVerificationSchema

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")
user_schema = UserSchema()
verification_schema = UserVerificationSchema()

ALLOWED_REDIRECTS = {
    value.strip()
    for value in os.getenv("ALLOWED_REDIRECTS", "").split(",")
    if value.strip()
}


@auth_bp.post("/<provider>")
def auth_start(provider: str):
    """Start the OAuth authentication process.

    Args:
        provider (str): The OAuth provider (e.g., 'google', 'linkedin').

    Returns:
        Response: A JSON response with the authentication URL.
    """
    if provider not in {"google", "linkedin"}:
        return error_response(400, "bad provider")
    data = request.get_json(silent=True) or {}
    default_redirect_uri = os.getenv(f"{provider.upper()}_REDIRECT_URI")
    requested_redirect = data.get("redirect_uri")
    redirect_uri = requested_redirect or default_redirect_uri
    if requested_redirect:
        if (
            requested_redirect not in ALLOWED_REDIRECTS
            and requested_redirect != default_redirect_uri
        ):
            return error_response(400, "invalid redirect")
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
        return error_response(400, "bad provider")
    try:
        code = request.args.get("code")
        state = request.args.get("state")
        if not code or not state:
            return error_response(400, "missing code or state")
        if state != session.get("state"):
            return error_response(401, "invalid state")
        nonce = session.get("nonce")
        redirect_uri = session.get("redirect_uri") or os.getenv(
            f"{provider.upper()}_REDIRECT_URI"
        )
        try:
            info = fetch_user_info(provider, code, redirect_uri, nonce)
        except Exception as exc:  # pragma: no cover - network failures
            return error_response(401, "oauth error", {"reason": str(exc)})
        email = info.get("email")
        if not email:
            return error_response(422, "email required")
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
            return error_response(422, str(exc))
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
        return error_response(400, "missing token")
    try:
        payload = decode_jwt(token)
    except Exception as exc:  # pragma: no cover - jwt errors
        return error_response(401, str(exc))
    return jsonify(
        {"valid": True, "sub": payload["sub"], "exp": payload["exp"]}
    )


@auth_bp.post("/verification/request")
def request_verification():
    """Create or refresh a verification challenge for a user."""

    payload = request.get_json(silent=True) or {}
    user_id = payload.get("user_id")
    method = payload.get("method")
    code = payload.get("code")
    expires_at_raw = payload.get("expires_at")

    if not isinstance(user_id, int):
        return error_response(422, "user_id must be an integer")
    if not isinstance(method, str) or not method.strip():
        return error_response(422, "method required")
    if not isinstance(code, str) or not code.strip():
        return error_response(422, "code required")

    expires_at = None
    if expires_at_raw is not None:
        try:
            expires_at = _parse_iso_datetime(str(expires_at_raw))
        except ValueError as exc:
            return error_response(422, str(exc))

    with session_scope() as db_session:
        repo = UserRepository(db_session)
        user = repo.get(user_id)
        if user is None:
            return error_response(404, "user not found")
        verification = repo.create_verification(
            user,
            method=method.strip(),
            code=code.strip(),
            expires_at=expires_at,
        )
        data = verification_schema.dump(verification)

    return jsonify({"verification": data}), 201


@auth_bp.post("/verification/confirm")
def confirm_verification():
    """Validate a verification challenge."""

    payload = request.get_json(silent=True) or {}
    verification_id = payload.get("verification_id")
    code = payload.get("code")
    if not isinstance(verification_id, int):
        return error_response(422, "verification_id must be an integer")
    if not isinstance(code, str) or not code.strip():
        return error_response(422, "code required")

    with session_scope() as db_session:
        repo = UserRepository(db_session)
        verification = repo.get_verification_by_id(verification_id)
        if verification is None:
            return error_response(404, "verification not found")
        success = repo.confirm_verification(
            verification,
            provided_code=code.strip(),
            at=datetime.now(timezone.utc),
        )
        data = verification_schema.dump(verification)

    status = 200 if success else 422
    return jsonify({"success": success, "verification": data}), status


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
            return error_response(404, "user not found")
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


def _parse_iso_datetime(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value)
    except ValueError as exc:
        # pragma: no cover - fallback for unsupported formats
        raise ValueError("invalid datetime format") from exc
