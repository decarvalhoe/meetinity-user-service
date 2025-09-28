"""JWT helper utilities for encoding/decoding tokens and enforcing auth."""

from datetime import datetime, timedelta, timezone
from functools import wraps

import jwt
from flask import current_app, has_app_context, jsonify, request

from src.config import Config, get_config


def _config() -> Config:
    """Return the active application configuration."""

    if has_app_context():
        app_config = current_app.config.get("APP_CONFIG")
        if isinstance(app_config, Config):
            return app_config
    return get_config()


def encode_jwt(user) -> str:
    """Encode a JWT for a given user.

    Args:
        user: The user object.

    Returns:
        str: The encoded JWT.
    """
    config = _config()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user.id,
        "email": user.email,
        "provider": user.provider,
        "iat": now,
        "exp": now + timedelta(minutes=config.jwt_ttl_minutes),
    }
    return jwt.encode(
        payload,
        config.jwt_secret,
        algorithm=config.jwt_algorithm,
    )


def decode_jwt(token: str):
    """Decode a JWT.

    Args:
        token (str): The JWT to decode.

    Returns:
        dict: The decoded JWT payload.
    """
    config = _config()
    return jwt.decode(
        token,
        config.jwt_secret,
        algorithms=[config.jwt_algorithm],
    )


def require_auth(fn):
    """Decorator to require JWT authentication for a route.

    Args:
        fn: The function to wrap.

    Returns:
        function: The wrapped function.
    """
    @wraps(fn)
    def wrapper(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return (
                jsonify({"error": {"code": 401, "message": "missing token"}}),
                401,
            )
        token = auth.split(" ", 1)[1]
        try:
            payload = decode_jwt(token)
        except jwt.PyJWTError as exc:  # pragma: no cover
            return jsonify({"error": {"code": 401, "message": str(exc)}}), 401
        request.user = payload
        return fn(*args, **kwargs)

    return wrapper
