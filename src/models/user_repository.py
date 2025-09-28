"""Repository for user persistence."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.models.user import User, UserPreference, UserSocialAccount


class UserRepository:
    """Encapsulate persistence logic for users and related aggregates."""

    def __init__(self, session: Session) -> None:
        self.session = session

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------
    def get(self, user_id: int) -> Optional[User]:
        return self.session.get(User, user_id)

    def get_by_email(self, email: str) -> Optional[User]:
        normalized = self._normalize_email(email)
        stmt = select(User).where(User.email == normalized)
        return self.session.execute(stmt).unique().scalar_one_or_none()

    # ------------------------------------------------------------------
    # Mutations
    # ------------------------------------------------------------------
    def upsert_oauth_user(
        self,
        *,
        email: str,
        provider: str,
        provider_user_id: Optional[str] = None,
        name: Optional[str] = None,
        photo_url: Optional[str] = None,
        company: Optional[str] = None,
        title: Optional[str] = None,
        location: Optional[str] = None,
        last_login: Optional[datetime] = None,
        social_profile_url: Optional[str] = None,
    ) -> User:
        """Create or update a user based on OAuth information."""

        normalized_email = self._normalize_email(email)
        self._validate_email(normalized_email)

        user = self.get_by_email(normalized_email)
        created = False
        if user is None:
            user = User(email=normalized_email)
            created = True
            self.session.add(user)
        else:
            user.email = normalized_email

        user.name = name or user.name
        user.photo_url = photo_url or user.photo_url
        user.company = company or user.company
        user.title = title or user.title
        user.location = location or user.location
        user.provider = provider
        user.provider_user_id = provider_user_id

        if last_login:
            user.touch_login(last_login)

        self._sync_social_account(
            user,
            provider=provider,
            provider_user_id=provider_user_id,
            display_name=name,
            profile_url=social_profile_url,
            connected_at=last_login,
        )

        if created:
            self.session.flush()

        return user

    def set_preferences(
        self,
        user: User,
        preferences: dict[str, Optional[str]],
    ) -> User:
        """Replace preferences with provided mapping."""

        existing = {pref.key: pref for pref in user.preferences}
        keys_to_remove = set(existing) - set(preferences)

        for key in keys_to_remove:
            self.session.delete(existing[key])

        for key, value in preferences.items():
            if key in existing:
                existing[key].value = value
            else:
                user.preferences.append(
                    UserPreference(key=key, value=value)
                )

        self.session.flush()
        return user

    def deactivate(self, user: User) -> None:
        user.is_active = False
        self.session.flush()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _normalize_email(email: str) -> str:
        return email.strip().lower()

    @staticmethod
    def _validate_email(email: str) -> None:
        if "@" not in email:
            raise ValueError("invalid email address")

    @staticmethod
    def _sync_social_account(
        user: User,
        *,
        provider: str,
        provider_user_id: Optional[str],
        display_name: Optional[str],
        profile_url: Optional[str],
        connected_at: Optional[datetime],
    ) -> None:
        match = next(
            (acc for acc in user.social_accounts if acc.provider == provider),
            None,
        )
        if match is None:
            match = UserSocialAccount(provider=provider)
            user.social_accounts.append(match)
        match.provider_user_id = provider_user_id
        match.display_name = display_name
        match.profile_url = profile_url
        match.last_connected_at = connected_at
