# -*- coding: utf-8 -*-
"""Authentication routes for the User Service.

This file defines the routes for OAuth authentication, token verification, and user profile retrieval.
"""

import os
from datetime import datetime, timezone

from flask import Blueprint, jsonify, request, session

from src.auth.jwt_handler import decode_jwt, encode_jwt, require_auth
from src.auth.oauth import (
    build_auth_url,
    fetch_user_info,
    generate_nonce,
    generate_state,
)
from src.models.user import get_user, upsert_user

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")

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
        user = upsert_user(
            email=email,
            name=info.get("name") or info.get("localizedFirstName"),
            photo_url=info.get("picture") or info.get("profilePicture"),
            provider=provider,
            provider_user_id=info.get("sub") or info.get("id"),
            last_login=datetime.now(timezone.utc),
        )
        token = encode_jwt(user)
        return jsonify(
            {
                "token": token,
                "user": {"id": user.id, "email": user.email, "name": user.name},
            }
        )
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
    user = get_user(user_id)
    if not user:
        return _error(404, "user not found")
    return jsonify(
        {"user": {"id": user.id, "email": user.email, "name": user.name}}
    )

