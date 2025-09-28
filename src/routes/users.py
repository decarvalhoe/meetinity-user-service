"""User profile CRUD and search endpoints."""

from __future__ import annotations

from typing import Mapping, Tuple

from flask import Blueprint, current_app, jsonify, request
from marshmallow import ValidationError

from src.db.session import session_scope
from src.models.user_repository import UserRepository
from src.routes.auth import _profile_cache_key
from src.routes.helpers import error_response
from src.schemas.user import UserSchema, UserUpdateSchema
from src.services.uploads import UploadError, save_user_photo
from src.utils.lists import normalize_string_list

users_bp = Blueprint("users", __name__, url_prefix="/users")

user_schema = UserSchema()
users_schema = UserSchema(many=True)
update_schema = UserUpdateSchema()

DEFAULT_SORT = ("created_at", "desc")
ALLOWED_SORT_FIELDS = {
    "created_at",
    "updated_at",
    "last_login",
    "experience_years",
    "name",
}


@users_bp.get("")
def list_users():
    """Return paginated users with optional filters."""

    try:
        page, per_page, sort, filters = _parse_listing_args(request.args)
    except ValueError as exc:
        return error_response(400, str(exc))

    with session_scope() as session:
        repo = UserRepository(session)
        items, total = repo.list_users(
            page=page,
            per_page=per_page,
            sort=sort,
            filters=filters,
        )
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

    with session_scope() as session:
        repo = UserRepository(session)
        user = repo.get(user_id)
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

    with session_scope() as session:
        repo = UserRepository(session)
        user = repo.get(user_id)
        if user is None:
            return error_response(404, "user not found")
        updated = repo.update_user(user, data)
        response = jsonify({"user": user_schema.dump(updated)})

    redis_client = current_app.extensions.get("redis_client")
    if redis_client:
        redis_client.delete(_profile_cache_key(user_id))

    return response


@users_bp.delete("/<int:user_id>")
def delete_user(user_id: int):
    """Delete a user profile."""

    with session_scope() as session:
        repo = UserRepository(session)
        user = repo.get(user_id)
        if user is None:
            return error_response(404, "user not found")
        repo.delete_user(user)

    redis_client = current_app.extensions.get("redis_client")
    if redis_client:
        redis_client.delete(_profile_cache_key(user_id))

    return "", 204


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

    with session_scope() as session:
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

    redis_client = current_app.extensions.get("redis_client")
    if redis_client:
        redis_client.delete(_profile_cache_key(user_id))

    return response


@users_bp.get("/search")
def search_users():
    """Search users by free text with optional filters."""

    query = (request.args.get("q") or "").strip()
    if not query:
        return error_response(400, "missing search query")

    try:
        page, per_page, sort, filters = _parse_listing_args(request.args)
    except ValueError as exc:
        return error_response(400, str(exc))

    with session_scope() as session:
        repo = UserRepository(session)
        items, total = repo.search_users(
            query=query,
            page=page,
            per_page=per_page,
            sort=sort,
            filters=filters,
        )
    return jsonify(
        {
            "items": users_schema.dump(items),
            "page": page,
            "per_page": per_page,
            "total": total,
            "query": query,
        }
    )


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
