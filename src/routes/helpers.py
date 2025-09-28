"""Shared route utilities."""

from __future__ import annotations

from typing import Any

from flask import current_app, jsonify

from src.models.repositories import RepositoryError


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


def repository_error_response(error: RepositoryError):
    """Log a repository error and convert it into an API response."""

    current_app.logger.exception("repository error: %s", error)
    return error_response(error.status_code, error.message, error.details)
