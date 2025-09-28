# -*- coding: utf-8 -*-
"""Authentication routes for the User Service."""

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
from src.models.repositories import RepositoryError, UserRepository
from src.routes.helpers import error_response, repository_error_response
from src.schemas.user import UserSchema, UserVerificationSchema
from src.services.audit import log_audit_event
from src.services.transactions import transactional_session

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
        log_audit_event(
            "auth.start.invalid_provider",
            actor=provider,
            details={"path": f"/auth/{provider}"},
        )
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
    log_audit_event(
        "auth.start",
        actor=provider,
        details={"redirect_uri": redirect_uri, "state": state},
    )
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
        log_audit_event(
            "auth.callback.invalid_provider",
            actor=provider,
            details={"path": f"/auth/{provider}/callback"},
        )
        return error_response(400, "bad provider")
    try:
        code = request.args.get("code")
        state = request.args.get("state")
        if not code or not state:
            log_audit_event(
                "auth.callback.missing_code",
                actor=provider,
                details={"state": state},
            )
            return error_response(400, "missing code or state")
        if state != session.get("state"):
            log_audit_event(
                "auth.callback.invalid_state",
                actor=provider,
                details={"expected": session.get("state"), "received": state},
            )
            return error_response(401, "invalid state")
        nonce = session.get("nonce")
        redirect_uri = session.get("redirect_uri") or os.getenv(
            f"{provider.upper()}_REDIRECT_URI"
        )
        try:
            info = fetch_user_info(provider, code, redirect_uri, nonce)
        except Exception as exc:  # pragma: no cover - network failures
            log_audit_event(
                "auth.callback.fetch_failed",
                actor=provider,
                details={"reason": str(exc)},
            )
            return error_response(401, "oauth error", {"reason": str(exc)})
        email = info.get("email")
        if not email:
            log_audit_event(
                "auth.callback.missing_email",
                actor=provider,
                details={"info": list(info.keys())},
            )
            return error_response(422, "email required")
        now = datetime.now(timezone.utc)
        cache_service = current_app.extensions.get("cache_service")
        try:
            with transactional_session(name="auth.oauth") as db_session:
                cache_hooks = (
                    cache_service.build_hooks() if cache_service else None
                )
                encryptor = current_app.extensions.get("encryptor")
                repo = UserRepository(
                    db_session,
                    cache_hooks=cache_hooks,
                    encryptor=encryptor,
                )
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
                log_audit_event(
                    "auth.callback.success",
                    session=db_session,
                    user_id=user.id,
                    actor=email,
                    details={"provider": provider},
                )
        except ValueError as exc:
            log_audit_event(
                "auth.callback.validation_error",
                actor=email,
                details={"provider": provider, "reason": str(exc)},
            )
            return error_response(422, str(exc))
        except RepositoryError as exc:
            log_audit_event(
                "auth.callback.repository_error",
                actor=email,
                details={"provider": provider, "message": str(exc)},
            )
            return repository_error_response(exc)
        if cache_service and cache_service.enabled:
            cache_service.set_json(
                cache_service.profile_key(user.id),
                profile,
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
        log_audit_event(
            "auth.verify.missing_token",
            details={"body": list(data.keys())},
        )
        return error_response(400, "missing token")
    try:
        payload = decode_jwt(token)
    except Exception as exc:  # pragma: no cover - jwt errors
        log_audit_event(
            "auth.verify.invalid",
            actor=None,
            details={"reason": str(exc)},
        )
        return error_response(401, str(exc))
    log_audit_event(
        "auth.verify.success",
        user_id=payload.get("sub"),
        actor=payload.get("email"),
        details={"exp": payload.get("exp")},
    )
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

    try:
        with transactional_session(
            name="auth.verification.request"
        ) as db_session:
            cache_service = current_app.extensions.get("cache_service")
            cache_hooks = (
                cache_service.build_hooks() if cache_service else None
            )
            encryptor = current_app.extensions.get("encryptor")
            repo = UserRepository(
                db_session,
                cache_hooks=cache_hooks,
                encryptor=encryptor,
            )
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
            log_audit_event(
                "auth.verification.request",
                session=db_session,
                user_id=user.id,
                actor=str(user.email),
                details={
                    "method": verification.method,
                    "expires_at": verification.expires_at.isoformat()
                    if verification.expires_at
                    else None,
                },
            )
    except RepositoryError as exc:
        return repository_error_response(exc)

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

    try:
        with transactional_session(
            name="auth.verification.confirm"
        ) as db_session:
            cache_service = current_app.extensions.get("cache_service")
            cache_hooks = (
                cache_service.build_hooks() if cache_service else None
            )
            encryptor = current_app.extensions.get("encryptor")
            repo = UserRepository(
                db_session, cache_hooks=cache_hooks, encryptor=encryptor
            )
            verification = repo.get_verification_by_id(verification_id)
            if verification is None:
                return error_response(404, "verification not found")
            success = repo.confirm_verification(
                verification,
                provided_code=code.strip(),
                at=datetime.now(timezone.utc),
            )
            data = verification_schema.dump(verification)
            log_audit_event(
                "auth.verification.confirm",
                session=db_session,
                user_id=verification.user_id,
                actor=str(verification.method),
                details={"success": success},
            )
    except RepositoryError as exc:
        return repository_error_response(exc)

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
    cache_service = current_app.extensions.get("cache_service")
    cache_key = None
    if cache_service and cache_service.enabled:
        cache_key = cache_service.profile_key(user_id)
        cached = cache_service.get_json(cache_key)
        if cached is not None:
            return jsonify({"user": cached})

    try:
        with transactional_session(name="auth.profile") as db_session:
            cache_hooks = (
                cache_service.build_hooks() if cache_service else None
            )
            encryptor = current_app.extensions.get("encryptor")
            repo = UserRepository(
                db_session, cache_hooks=cache_hooks, encryptor=encryptor
            )
            user = repo.get(user_id)
            if not user:
                return error_response(404, "user not found")
            profile = _serialize_user(user)
    except RepositoryError as exc:
        return repository_error_response(exc)

    if cache_service and cache_key:
        cache_service.set_json(cache_key, profile)

    return jsonify({"user": profile})


def _serialize_user(user) -> Dict[str, Any]:
    """Serialize a user object for JSON responses/caching."""

    return user_schema.dump(user)


def _parse_iso_datetime(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value)
    except ValueError as exc:
        # pragma: no cover - fallback for unsupported formats
        raise ValueError("invalid datetime format") from exc
