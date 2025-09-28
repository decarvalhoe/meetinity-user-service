"""User profile CRUD and search endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Callable, Mapping, Tuple, TypeVar

from flask import Blueprint, Response, current_app, jsonify, request
from marshmallow import ValidationError

from src.models.repositories import RepositoryError, UserRepository
from src.routes.auth import _profile_cache_key
from src.routes.helpers import error_response, repository_error_response
from src.schemas.user import (
    UserActivitySchema,
    UserConnectionSchema,
    UserSchema,
    UserSessionSchema,
    UserVerificationSchema,
    UserUpdateSchema,
)
from src.services.uploads import UploadError, save_user_photo
from src.services.transactions import transactional_session
from src.utils.lists import normalize_string_list

users_bp = Blueprint("users", __name__, url_prefix="/users")

user_schema = UserSchema()
users_schema = UserSchema(many=True)
update_schema = UserUpdateSchema()
activity_schema = UserActivitySchema()
activities_schema = UserActivitySchema(many=True)
session_schema = UserSessionSchema()
sessions_schema = UserSessionSchema(many=True)
connection_schema = UserConnectionSchema()
connections_schema = UserConnectionSchema(many=True)
verification_schema = UserVerificationSchema()

DEFAULT_SORT = ("created_at", "desc")
ALLOWED_SORT_FIELDS = {
    "created_at",
    "updated_at",
    "last_login",
    "experience_years",
    "name",
}


T = TypeVar("T")


def _execute_user_repo(
    transaction_name: str, handler: Callable[[UserRepository], T]
) -> tuple[T | None, Response | tuple | None]:
    try:
        with transactional_session(name=transaction_name) as session:
            repository = UserRepository(session)
            return handler(repository), None
    except RepositoryError as exc:
        return None, repository_error_response(exc)


@users_bp.get("")
def list_users():
    """Return paginated users with optional filters."""

    try:
        page, per_page, sort, filters = _parse_listing_args(request.args)
    except ValueError as exc:
        return error_response(400, str(exc))

    result, error = _execute_user_repo(
        "users.list",
        lambda repo: repo.list_users(
            page=page,
            per_page=per_page,
            sort=sort,
            filters=filters,
        ),
    )
    if error:
        return error
    items, total = result
    return jsonify(
        {
            "items": users_schema.dump(items),
            "page": page,
            "per_page": per_page,
            "total": total,
        }
    )


@users_bp.get("/<int:user_id>")
def get_user(user_id: int):
    """Return a single user profile."""

    user, error = _execute_user_repo(
        "users.get", lambda repo: repo.get(user_id)
    )
    if error:
        return error
    if user is None:
        return error_response(404, "user not found")
    return jsonify({"user": user_schema.dump(user)})


@users_bp.put("/<int:user_id>")
def update_user(user_id: int):
    """Update a user profile."""

    payload = request.get_json(silent=True)
    if payload is None:
        return error_response(400, "missing request body")
    try:
        data = update_schema.load(payload)
    except ValidationError as exc:
        return error_response(422, "invalid payload", exc.messages)

    try:
        with transactional_session(name="users.update") as session:
            repo = UserRepository(session)
            user = repo.get(user_id)
            if user is None:
                return error_response(404, "user not found")
            updated = repo.update_user(user, data)
            response = jsonify({"user": user_schema.dump(updated)})
    except RepositoryError as exc:
        return repository_error_response(exc)

    _invalidate_profile_cache(user_id)

    return response


@users_bp.delete("/<int:user_id>")
def delete_user(user_id: int):
    """Delete a user profile."""

    try:
        with transactional_session(name="users.delete") as session:
            repo = UserRepository(session)
            user = repo.get(user_id)
            if user is None:
                return error_response(404, "user not found")
            repo.delete_user(user)
    except RepositoryError as exc:
        return repository_error_response(exc)

    _invalidate_profile_cache(user_id)

    return "", 204


@users_bp.put("/<int:user_id>/preferences")
def upsert_preferences(user_id: int):
    """Replace preferences for a user."""

    payload = request.get_json(silent=True)
    if not isinstance(payload, dict) or "preferences" not in payload:
        return error_response(400, "preferences payload required")
    preferences = payload["preferences"]
    if not isinstance(preferences, dict):
        return error_response(400, "preferences must be an object")

    normalized: dict[str, str | None] = {}
    for key, value in preferences.items():
        if not isinstance(key, str) or not key.strip():
            return error_response(422, "invalid preference key")
        normalized[key.strip()] = None if value is None else str(value)

    try:
        with transactional_session(name="users.preferences") as session:
            repo = UserRepository(session)
            user = repo.get(user_id)
            if user is None:
                return error_response(404, "user not found")
            repo.set_preferences(user, normalized)
            serialized = user_schema.dump(user)
    except RepositoryError as exc:
        return repository_error_response(exc)

    _invalidate_profile_cache(user_id)
    return jsonify(
        {"preferences": serialized["preferences"], "user_id": user_id}
    )


@users_bp.put("/<int:user_id>/privacy")
def update_privacy(user_id: int):
    """Persist privacy settings and active tokens."""

    payload = request.get_json(silent=True)
    if payload is None:
        return error_response(400, "missing request body")
    privacy_settings = payload.get("privacy_settings")
    if privacy_settings is not None and not isinstance(privacy_settings, dict):
        return error_response(422, "privacy_settings must be an object")
    active_tokens = payload.get("active_tokens")
    if active_tokens is not None and not isinstance(active_tokens, list):
        return error_response(422, "active_tokens must be a list")

    try:
        with transactional_session(name="users.privacy") as session:
            repo = UserRepository(session)
            user = repo.get(user_id)
            if user is None:
                return error_response(404, "user not found")
            repo.update_privacy(
                user,
                privacy_settings=privacy_settings,
                active_tokens=active_tokens,
            )
            serialized = user_schema.dump(user)
    except RepositoryError as exc:
        return repository_error_response(exc)

    _invalidate_profile_cache(user_id)
    return jsonify({"user": serialized})


@users_bp.get("/<int:user_id>/privacy")
def get_privacy(user_id: int):
    """Return stored privacy metadata for a user."""

    user, error = _execute_user_repo(
        "users.privacy.get", lambda repo: repo.get(user_id)
    )
    if error:
        return error
    if user is None:
        return error_response(404, "user not found")
    payload = {
        "user_id": user_id,
        "privacy_settings": user.privacy_settings or {},
        "privacy_level": user.privacy_level,
        "active_tokens": user.active_tokens or [],
    }
    return jsonify(payload)


@users_bp.post("/<int:user_id>/verify")
def verify_user(user_id: int):
    """Confirm a verification code for a user."""

    payload = request.get_json(silent=True)
    if payload is None:
        return error_response(400, "missing request body")
    method = payload.get("method")
    code = payload.get("code")
    if not isinstance(method, str) or not method.strip():
        return error_response(422, "verification method required")
    if not isinstance(code, str) or not code.strip():
        return error_response(422, "verification code required")

    try:
        with transactional_session(name="users.verify") as session:
            repo = UserRepository(session)
            user = repo.get(user_id)
            if user is None:
                return error_response(404, "user not found")
            verification = repo.get_verification(user_id, method.strip())
            if verification is None:
                return error_response(404, "verification not found")
            success = repo.confirm_verification(
                verification,
                provided_code=code.strip(),
            )
            verification_payload = verification_schema.dump(verification)
            user_payload = user_schema.dump(user)
            status = verification.status
    except RepositoryError as exc:
        return repository_error_response(exc)

    if success:
        _invalidate_profile_cache(user_id)
        response = jsonify(
            {
                "verified": True,
                "verification": verification_payload,
                "user": user_payload,
            }
        )
        response.status_code = 200
        return response

    reason = "expired" if status == "expired" else "invalid_code"
    response = jsonify(
        {
            "verified": False,
            "reason": reason,
            "verification": verification_payload,
            "user": user_payload,
        }
    )
    response.status_code = 409
    return response


@users_bp.post("/<int:user_id>/deactivate")
def deactivate_user(user_id: int):
    """Deactivate a user profile and optionally schedule reactivation."""

    payload = request.get_json(silent=True) or {}
    reactivation_raw = payload.get("reactivate_at") or payload.get(
        "reactivation_at"
    )
    reactivation_at = None
    if reactivation_raw:
        try:
            reactivation_at = _parse_iso_datetime(str(reactivation_raw))
        except ValueError as exc:
            return error_response(422, str(exc))

    try:
        with transactional_session(name="users.deactivate") as session:
            repo = UserRepository(session)
            user = repo.get(user_id)
            if user is None:
                return error_response(404, "user not found")
            updated = repo.deactivate(user, reactivation_at=reactivation_at)
            user_payload = user_schema.dump(updated)
    except RepositoryError as exc:
        return repository_error_response(exc)

    _invalidate_profile_cache(user_id)
    response = jsonify(
        {
            "user": user_payload,
            "deactivated_at": user_payload.get("deactivated_at"),
            "reactivation_at": user_payload.get("reactivation_at"),
        }
    )
    response.status_code = 200
    return response


@users_bp.post("/<int:user_id>/photo")
def upload_photo(user_id: int):
    """Upload and associate a profile photo."""

    file = request.files.get("photo")
    if file is None:
        return error_response(400, "photo file required")

    upload_folder = current_app.config.get("UPLOAD_FOLDER")
    if not upload_folder:
        return error_response(500, "upload folder not configured")
    url_prefix = current_app.config.get(
        "UPLOAD_URL_PREFIX",
        "/uploads",
    )

    try:
        with transactional_session(name="users.photo") as session:
            repo = UserRepository(session)
            user = repo.get(user_id)
            if user is None:
                return error_response(404, "user not found")
            try:
                photo_url = save_user_photo(
                    file,
                    user_id=user.id,
                    upload_folder=upload_folder,
                    url_prefix=url_prefix,
                )
            except UploadError as exc:
                return error_response(422, str(exc))
            repo.set_photo_url(user, photo_url)
            response = jsonify({"photo_url": photo_url, "user_id": user.id})
            response.status_code = 201
    except RepositoryError as exc:
        return repository_error_response(exc)

    redis_client = current_app.extensions.get("redis_client")
    if redis_client:
        redis_client.delete(_profile_cache_key(user_id))

    return response


@users_bp.post("/<int:user_id>/activities")
def log_activity(user_id: int):
    """Record a user activity entry."""

    payload = request.get_json(silent=True)
    if payload is None:
        return error_response(400, "missing request body")
    activity_type = payload.get("activity_type")
    if not isinstance(activity_type, str) or not activity_type.strip():
        return error_response(422, "activity_type required")
    description = payload.get("description")
    score_delta = payload.get("score_delta", 0)
    try:
        score_delta_int = int(score_delta)
    except (TypeError, ValueError):
        return error_response(422, "score_delta must be an integer")

    try:
        with transactional_session(name="users.activity") as session:
            repo = UserRepository(session)
            user = repo.get(user_id)
            if user is None:
                return error_response(404, "user not found")
            activity = repo.record_activity(
                user,
                activity_type=activity_type.strip(),
                description=description,
                score_delta=score_delta_int,
            )
            response = jsonify({"activity": activity_schema.dump(activity)})
            response.status_code = 201
    except RepositoryError as exc:
        return repository_error_response(exc)

    _invalidate_profile_cache(user_id)
    return response


@users_bp.get("/<int:user_id>/activities")
def list_activities(user_id: int):
    """List recent activities for a user."""

    try:
        limit = _parse_int(
            request.args.get("limit"),
            default=50,
            min_value=1,
            max_value=200,
        )
    except ValueError as exc:
        return error_response(400, str(exc))

    try:
        with transactional_session(name="users.activities.list") as session:
            repo = UserRepository(session)
            user = repo.get(user_id)
            if user is None:
                return error_response(404, "user not found")
            activities = repo.list_activities(user, limit=limit)
    except RepositoryError as exc:
        return repository_error_response(exc)
    return jsonify(
        {"items": activities_schema.dump(activities), "total": len(activities)}
    )


@users_bp.get("/search")
def search_users():
    """Search users by free text with optional filters."""

    query = (request.args.get("q") or "").strip()
    if not query:
        return error_response(400, "missing search query")

    try:
        page, per_page, sort, filters = _parse_listing_args(request.args)
        recommendation_limit = _parse_int(
            request.args.get("recommendations"),
            default=5,
            min_value=1,
            max_value=20,
        )
    except ValueError as exc:
        return error_response(400, str(exc))

    result, error = _execute_user_repo(
        "users.search",
        lambda repo: repo.search_users(
            query=query,
            page=page,
            per_page=per_page,
            sort=sort,
            filters=filters,
            include_recommendations=True,
            recommendation_limit=recommendation_limit or 5,
        ),
    )
    if error:
        return error
    items, total, recommendations = result
    return jsonify(
        {
            "items": users_schema.dump(items),
            "page": page,
            "per_page": per_page,
            "total": total,
            "query": query,
            "recommendations": users_schema.dump(recommendations),
            "recommendation_limit": recommendation_limit or 5,
        }
    )


@users_bp.get("/discover")
def discover_users():
    """Expose discovery recommendations based on activity and skills."""

    query = (request.args.get("q") or "").strip()

    try:
        page, per_page, sort, filters = _parse_listing_args(request.args)
        recommendation_limit = _parse_int(
            request.args.get("recommendations"),
            default=6,
            min_value=1,
            max_value=20,
        )
    except ValueError as exc:
        return error_response(400, str(exc))

    base_user_id = request.args.get("user_id")
    try:
        with transactional_session(name="users.discover") as session:
            repo = UserRepository(session)
            base_user = None
            if base_user_id:
                try:
                    parsed_id = int(base_user_id)
                except (TypeError, ValueError):
                    return error_response(400, "invalid user_id")
                base_user = repo.get(parsed_id)
                if base_user is None:
                    return error_response(404, "user not found")
            items, total, recommendations = repo.search_users(
                query=query,
                page=page,
                per_page=per_page,
                sort=sort,
                filters=filters,
                include_recommendations=True,
                base_user=base_user,
                recommendation_limit=recommendation_limit or 6,
            )
            context_user_id = base_user.id if base_user else None
    except RepositoryError as exc:
        return repository_error_response(exc)

    return jsonify(
        {
            "items": users_schema.dump(items),
            "total": total,
            "page": page,
            "per_page": per_page,
            "query": query,
            "recommendations": users_schema.dump(recommendations),
            "recommendation_limit": recommendation_limit or 6,
            "context_user_id": context_user_id,
        }
    )


@users_bp.post("/<int:user_id>/sessions")
def create_session(user_id: int):
    """Create an encrypted session for a user."""

    payload = request.get_json(silent=True)
    if payload is None:
        return error_response(400, "missing request body")
    session_token = payload.get("session_token")
    if not isinstance(session_token, str) or not session_token.strip():
        return error_response(422, "session_token required")
    expires_at_raw = payload.get("expires_at")
    expires_at = None
    if expires_at_raw is not None:
        try:
            expires_at = _parse_iso_datetime(str(expires_at_raw))
        except ValueError as exc:
            return error_response(422, str(exc))

    try:
        with transactional_session(name="users.sessions.create") as session:
            repo = UserRepository(session)
            user = repo.get(user_id)
            if user is None:
                return error_response(404, "user not found")
            record = repo.create_session(
                user,
                session_token=session_token.strip(),
                encrypted_payload=payload.get("encrypted_payload"),
                ip_address=payload.get("ip_address"),
                user_agent=payload.get("user_agent"),
                expires_at=expires_at,
            )
            response = jsonify({"session": session_schema.dump(record)})
            response.status_code = 201
    except RepositoryError as exc:
        return repository_error_response(exc)

    _invalidate_profile_cache(user_id)
    return response


@users_bp.get("/<int:user_id>/sessions")
def list_sessions(user_id: int):
    """List encrypted sessions for a user."""

    try:
        with transactional_session(name="users.sessions.list") as session:
            repo = UserRepository(session)
            user = repo.get(user_id)
            if user is None:
                return error_response(404, "user not found")
            records = repo.list_sessions(user)
    except RepositoryError as exc:
        return repository_error_response(exc)
    return jsonify(
        {"items": sessions_schema.dump(records), "total": len(records)}
    )


@users_bp.delete("/<int:user_id>/sessions/<int:session_id>")
def revoke_session(user_id: int, session_id: int):
    """Revoke a session token."""

    try:
        with transactional_session(name="users.sessions.revoke") as session:
            repo = UserRepository(session)
            record = repo.get_session_by_id(session_id)
            if record is None or record.user_id != user_id:
                return error_response(404, "session not found")
            repo.revoke_session(record)
    except RepositoryError as exc:
        return repository_error_response(exc)

    _invalidate_profile_cache(user_id)
    return "", 204


@users_bp.post("/<int:user_id>/connections")
def create_connection(user_id: int):
    """Create an extended social connection."""

    payload = request.get_json(silent=True)
    if payload is None:
        return error_response(400, "missing request body")
    connection_type = payload.get("connection_type")
    if not isinstance(connection_type, str) or not connection_type.strip():
        return error_response(422, "connection_type required")
    attributes = payload.get("attributes")
    if attributes is not None and not isinstance(attributes, dict):
        return error_response(422, "attributes must be an object")

    try:
        with transactional_session(name="users.connections.create") as session:
            repo = UserRepository(session)
            user = repo.get(user_id)
            if user is None:
                return error_response(404, "user not found")
            connection = repo.create_connection(
                user,
                connection_type=connection_type.strip(),
                status=payload.get("status", "pending"),
                target_user_id=payload.get("target_user_id"),
                external_reference=payload.get("external_reference"),
                attributes=attributes,
            )
            response = jsonify(
                {"connection": connection_schema.dump(connection)}
            )
            response.status_code = 201
    except RepositoryError as exc:
        return repository_error_response(exc)
    _invalidate_profile_cache(user_id)
    return response


@users_bp.get("/<int:user_id>/connections")
def list_connections(user_id: int):
    """List social connections for a user."""

    status = request.args.get("status")
    try:
        with transactional_session(name="users.connections.list") as session:
            repo = UserRepository(session)
            user = repo.get(user_id)
            if user is None:
                return error_response(404, "user not found")
            connections = repo.list_connections(user, status=status or None)
    except RepositoryError as exc:
        return repository_error_response(exc)
    return jsonify(
        {
            "items": connections_schema.dump(connections),
            "total": len(connections),
        }
    )


@users_bp.patch("/<int:user_id>/connections/<int:connection_id>")
def update_connection(user_id: int, connection_id: int):
    """Update connection status or metadata."""

    payload = request.get_json(silent=True)
    if payload is None:
        return error_response(400, "missing request body")
    status = payload.get("status")
    if status is not None and (
        not isinstance(status, str) or not status.strip()
    ):
        return error_response(422, "invalid status")
    attributes = payload.get("attributes")
    if attributes is not None and not isinstance(attributes, dict):
        return error_response(422, "attributes must be an object")

    try:
        with transactional_session(name="users.connections.update") as session:
            repo = UserRepository(session)
            connection = repo.get_connection_by_id(connection_id)
            if connection is None or connection.user_id != user_id:
                return error_response(404, "connection not found")
            updated = repo.update_connection_status(
                connection,
                status=status or connection.status,
                attributes=attributes,
            )
            result = connection_schema.dump(updated)
    except RepositoryError as exc:
        return repository_error_response(exc)

    _invalidate_profile_cache(user_id)
    return jsonify({"connection": result})


@users_bp.delete("/<int:user_id>/connections/<int:connection_id>")
def delete_connection(user_id: int, connection_id: int):
    """Remove a connection."""

    try:
        with transactional_session(name="users.connections.delete") as session:
            repo = UserRepository(session)
            connection = repo.get_connection_by_id(connection_id)
            if connection is None or connection.user_id != user_id:
                return error_response(404, "connection not found")
            repo.delete_connection(connection)
    except RepositoryError as exc:
        return repository_error_response(exc)
    _invalidate_profile_cache(user_id)
    return "", 204


def _parse_listing_args(
    args: Mapping[str, str],
) -> Tuple[int, int, Tuple[str, str], dict[str, object]]:
    """Parse pagination, sorting, and filter arguments."""

    page = _parse_int(args.get("page"), default=1, min_value=1)
    per_page = _parse_int(
        args.get("per_page"),
        default=20,
        min_value=1,
        max_value=100,
    )
    sort = _parse_sort(args.get("sort"))

    filters: dict[str, object] = {}
    for key in ("industry", "location"):
        value = (args.get(key) or "").strip()
        if value:
            filters[key] = value

    min_exp = _parse_int(args.get("min_experience"), default=None, min_value=0)
    max_exp = _parse_int(args.get("max_experience"), default=None, min_value=0)
    if min_exp is not None:
        filters["min_experience"] = min_exp
    if max_exp is not None:
        filters["max_experience"] = max_exp
    if (
        min_exp is not None
        and max_exp is not None
        and max_exp < min_exp
    ):
        raise ValueError(
            "max_experience must be greater than or equal to min_experience"
        )

    skills_raw = args.get("skills")
    if skills_raw:
        skills = normalize_string_list(skills_raw.split(","))
        if skills:
            filters["skills"] = skills

    return page, per_page, sort, filters


def _parse_int(
    value: str | None,
    *,
    default: int | None,
    min_value: int | None = None,
    max_value: int | None = None,
) -> int | None:
    if value in (None, ""):
        return default
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid integer: {value}") from exc
    if min_value is not None and parsed < min_value:
        raise ValueError(f"value must be >= {min_value}")
    if max_value is not None and parsed > max_value:
        raise ValueError(f"value must be <= {max_value}")
    return parsed


def _parse_sort(sort_value: str | None) -> Tuple[str, str]:
    raw = (sort_value or "").strip() or "created_at:desc"
    field, _, direction = raw.partition(":")
    field = field or DEFAULT_SORT[0]
    direction = direction or DEFAULT_SORT[1]
    direction = direction.lower()
    if field not in ALLOWED_SORT_FIELDS:
        raise ValueError("invalid sort field")
    if direction not in {"asc", "desc"}:
        raise ValueError("invalid sort direction")
    return field, direction


def _parse_iso_datetime(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value)
    except ValueError as exc:  # pragma: no cover - python <3.11 compatibility
        raise ValueError("invalid datetime format") from exc


def _invalidate_profile_cache(user_id: int) -> None:
    redis_client = current_app.extensions.get("redis_client")
    if redis_client:
        redis_client.delete(_profile_cache_key(user_id))
