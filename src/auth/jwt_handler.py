import os
from datetime import datetime, timedelta, timezone
from functools import wraps

import jwt
from flask import jsonify, request

JWT_SECRET = os.getenv("JWT_SECRET", "change_me")
JWT_ALGO = os.getenv("JWT_ALGO", "HS256")
JWT_TTL_MIN = int(os.getenv("JWT_TTL_MIN", "60"))


def encode_jwt(user) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user.id,
        "email": user.email,
        "provider": user.provider,
        "iat": now,
        "exp": now + timedelta(minutes=JWT_TTL_MIN),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)


def decode_jwt(token: str):
    return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])


def require_auth(fn):
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
