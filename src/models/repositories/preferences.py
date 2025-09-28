"""Persistence helpers for user preferences and privacy."""

from __future__ import annotations

from typing import Iterable, Optional

from src.models.user import User, UserPreference

from .base import SQLAlchemyRepository, repository_method
from .users import normalize_tokens


class UserPreferenceRepository(SQLAlchemyRepository):
    """Manage user preference records."""

    @repository_method
    def set_preferences(
        self,
        user: User,
        preferences: dict[str, Optional[str]],
    ) -> User:
        existing = {pref.key: pref for pref in user.preferences}
        keys_to_remove = set(existing) - set(preferences)

        for key in keys_to_remove:
            self.session.delete(existing[key])

        for key, value in preferences.items():
            if key in existing:
                existing[key].value = value
            else:
                user.preferences.append(UserPreference(key=key, value=value))

        self._flush()
        self._invalidate_profile_cache(user.id)
        return user

    @repository_method
    def update_privacy(
        self,
        user: User,
        *,
        privacy_settings: Optional[dict[str, object]] = None,
        active_tokens: Optional[Iterable[str]] = None,
    ) -> User:
        if privacy_settings is not None:
            user.privacy_settings = dict(privacy_settings)
        if active_tokens is not None:
            user.active_tokens = normalize_tokens(active_tokens)
        self._flush()
        self._invalidate_profile_cache(user.id)
        return user


__all__ = ["UserPreferenceRepository"]
