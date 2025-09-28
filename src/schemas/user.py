"""User-related Marshmallow schemas."""
from __future__ import annotations

from typing import Any, Iterable

from marshmallow import Schema, fields, post_dump


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
    provider = fields.String(allow_none=True)
    provider_user_id = fields.String(allow_none=True)
    last_login = fields.DateTime(allow_none=True)
    last_active_at = fields.DateTime(allow_none=True)
    bio = fields.String(allow_none=True)
    timezone = fields.String(allow_none=True)
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
        return data
