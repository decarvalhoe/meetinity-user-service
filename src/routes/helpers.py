"""Shared route utilities."""

from __future__ import annotations

from typing import Any

from flask import jsonify


def error_response(
    status_code: int,
    message: str,
    details: dict[str, Any] | None = None,
):
    """Return a standardized JSON error response."""

    payload = {
        "error": {
            "code": status_code,
            "message": message,
            "details": details or {},
        }
    }
    return jsonify(payload), status_code
