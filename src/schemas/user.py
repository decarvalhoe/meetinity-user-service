"""User-related Marshmallow schemas."""
from __future__ import annotations

from typing import Any, Iterable

from marshmallow import (
    Schema,
    ValidationError,
    fields,
    post_dump,
    post_load,
    pre_load,
    validates_schema,
)
from marshmallow.validate import Length, Range, URL

from src.utils.lists import decode_string_list, normalize_string_list


class UserSocialAccountSchema(Schema):
    """Schema for serializing linked social accounts."""

    provider = fields.String(required=True)
    provider_user_id = fields.String(allow_none=True)
    display_name = fields.String(allow_none=True)
    profile_url = fields.String(allow_none=True)
    last_connected_at = fields.DateTime(allow_none=True)


class UserSchema(Schema):
    """Schema for serializing ``User`` ORM instances."""

    id = fields.Integer(required=True)
    email = fields.Email(required=True)
    name = fields.String(allow_none=True)
    photo_url = fields.String(allow_none=True)
    title = fields.String(allow_none=True)
    company = fields.String(allow_none=True)
    location = fields.String(allow_none=True)
    industry = fields.String(allow_none=True)
    linkedin_url = fields.String(allow_none=True)
    experience_years = fields.Integer(allow_none=True)
    provider = fields.String(allow_none=True)
    provider_user_id = fields.String(allow_none=True)
    last_login = fields.DateTime(allow_none=True)
    last_active_at = fields.DateTime(allow_none=True)
    bio = fields.String(allow_none=True)
    timezone = fields.String(allow_none=True)
    skills = fields.Method("_dump_skills")
    interests = fields.Method("_dump_interests")
    is_active = fields.Boolean()
    preferences = fields.Method("_dump_preferences")
    social_accounts = fields.List(
        fields.Nested(UserSocialAccountSchema),
        dump_default=list,
    )

    @staticmethod
    def _dump_preferences(obj: Any) -> dict[str, Any]:
        preferences: Iterable[Any] | None = getattr(
            obj,
            "preferences",
            None,
        )
        if not preferences:
            return {}
        return {
            pref.key: pref.value
            for pref in preferences
        }

    @post_dump
    def ensure_defaults(
        self,
        data: dict[str, Any],
        **_: Any,
    ) -> dict[str, Any]:
        data.setdefault("preferences", {})
        data.setdefault("social_accounts", [])
        data.setdefault("skills", [])
        data.setdefault("interests", [])
        return data

    @staticmethod
    def _dump_skills(obj: Any) -> list[str]:
        return decode_string_list(getattr(obj, "skills", None))

    @staticmethod
    def _dump_interests(obj: Any) -> list[str]:
        return decode_string_list(getattr(obj, "interests", None))


class UserUpdateSchema(Schema):
    """Schema for validating user updates."""

    name = fields.String(validate=Length(min=1, max=120))
    title = fields.String(validate=Length(max=120))
    company = fields.String(validate=Length(max=120))
    location = fields.String(validate=Length(max=120))
    industry = fields.String(validate=Length(max=120))
    linkedin_url = fields.String(validate=URL(), allow_none=True)
    experience_years = fields.Integer(validate=Range(min=0, max=100))
    bio = fields.String(validate=Length(max=2000))
    timezone = fields.String(validate=Length(max=64))
    is_active = fields.Boolean()
    skills = fields.List(
        fields.String(validate=Length(min=1, max=60)),
        load_default=None,
    )
    interests = fields.List(
        fields.String(validate=Length(min=1, max=60)),
        load_default=None,
    )

    @post_load
    def _normalize_lists(
        self,
        data: dict[str, Any],
        **_: Any,
    ) -> dict[str, Any]:
        for key in ("skills", "interests"):
            if key in data and data[key] is not None:
                data[key] = normalize_string_list(data[key])
        if "linkedin_url" in data and not data["linkedin_url"]:
            data["linkedin_url"] = None
        return data

    @pre_load
    def _coerce_blank(
        self,
        data: dict[str, Any],
        **_: Any,
    ) -> dict[str, Any]:
        if isinstance(data, dict) and data.get("linkedin_url", None) == "":
            data["linkedin_url"] = None
        return data

    @validates_schema
    def _ensure_payload(self, data: dict[str, Any], **_: Any) -> None:
        if not data:
            raise ValidationError("no fields provided")
