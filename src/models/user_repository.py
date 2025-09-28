"""Repository for user persistence."""

from __future__ import annotations

from datetime import datetime
from typing import Iterable, Optional, Sequence, Tuple

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from src.models.user import User, UserPreference, UserSocialAccount
from src.utils.lists import encode_string_list


SORT_FIELDS = {
    "created_at": User.created_at,
    "updated_at": User.updated_at,
    "last_login": User.last_login,
    "experience_years": User.experience_years,
    "name": User.name,
}


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

    def create_user(
        self,
        *,
        email: str,
        name: Optional[str] = None,
        title: Optional[str] = None,
        company: Optional[str] = None,
        location: Optional[str] = None,
        industry: Optional[str] = None,
        linkedin_url: Optional[str] = None,
        experience_years: Optional[int] = None,
        bio: Optional[str] = None,
        skills: Iterable[str] | None = None,
        interests: Iterable[str] | None = None,
        timezone: Optional[str] = None,
        is_active: bool = True,
    ) -> User:
        """Create a new user record."""

        normalized_email = self._normalize_email(email)
        self._validate_email(normalized_email)

        user = User(
            email=normalized_email,
            name=name,
            title=title,
            company=company,
            location=location,
            industry=industry,
            linkedin_url=linkedin_url,
            experience_years=experience_years,
            bio=bio,
            timezone=timezone,
            skills=encode_string_list(skills),
            interests=encode_string_list(interests),
            is_active=is_active,
        )
        self.session.add(user)
        self.session.flush()
        return user

    def update_user(
        self,
        user: User,
        data: dict[str, object],
    ) -> User:
        """Update user attributes from a payload."""

        mapping = {
            "name": "name",
            "title": "title",
            "company": "company",
            "location": "location",
            "industry": "industry",
            "linkedin_url": "linkedin_url",
            "experience_years": "experience_years",
            "bio": "bio",
            "timezone": "timezone",
            "is_active": "is_active",
        }
        for field, attr in mapping.items():
            if field in data:
                setattr(user, attr, data[field])

        if "skills" in data:
            user.skills = encode_string_list(data.get("skills"))
        if "interests" in data:
            user.interests = encode_string_list(data.get("interests"))

        self.session.flush()
        return user

    def delete_user(self, user: User) -> None:
        """Remove a user from the database."""

        self.session.delete(user)
        self.session.flush()

    def set_photo_url(self, user: User, photo_url: str) -> User:
        """Persist a user's photo URL."""

        user.photo_url = photo_url
        self.session.flush()
        return user

    def list_users(
        self,
        *,
        page: int,
        per_page: int,
        sort: Tuple[str, str],
        filters: dict[str, object],
    ) -> Tuple[list[User], int]:
        """Return paginated users matching filters."""

        stmt = select(User)
        stmt = stmt.where(User.is_active.is_(True))
        stmt = self._apply_filters(stmt, filters)
        return self._paginate(stmt, page, per_page, sort)

    def search_users(
        self,
        *,
        query: str,
        page: int,
        per_page: int,
        sort: Tuple[str, str],
        filters: dict[str, object],
    ) -> Tuple[list[User], int]:
        """Search users by free-text query and filters."""

        stmt = select(User).where(User.is_active.is_(True))
        stmt = self._apply_filters(stmt, filters)
        pattern = f"%{query.lower()}%"
        stmt = stmt.where(
            or_(
                func.lower(User.name).like(pattern),
                func.lower(User.title).like(pattern),
                func.lower(User.company).like(pattern),
                func.lower(User.bio).like(pattern),
                func.lower(func.coalesce(User.skills, "")).like(pattern),
                func.lower(func.coalesce(User.interests, "")).like(pattern),
            )
        )
        return self._paginate(stmt, page, per_page, sort)

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

    def _apply_filters(self, stmt, filters: dict[str, object]):
        if industry := filters.get("industry"):
            stmt = stmt.where(User.industry == industry)
        if location := filters.get("location"):
            stmt = stmt.where(User.location == location)
        if (min_exp := filters.get("min_experience")) is not None:
            stmt = stmt.where(User.experience_years >= int(min_exp))
        if (max_exp := filters.get("max_experience")) is not None:
            stmt = stmt.where(User.experience_years <= int(max_exp))
        skills = filters.get("skills")
        if isinstance(skills, Sequence):
            for skill in skills:
                stmt = stmt.where(User.skills.contains(f'"{skill}"'))
        return stmt

    def _paginate(
        self,
        stmt,
        page: int,
        per_page: int,
        sort: Tuple[str, str],
    ) -> Tuple[list[User], int]:
        sort_field, direction = sort
        column = SORT_FIELDS.get(sort_field, User.created_at)
        order_clause = column.desc() if direction == "desc" else column.asc()

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = self.session.execute(count_stmt).scalar_one()
        if total == 0:
            return [], 0

        offset = (page - 1) * per_page
        result_stmt = (
            stmt.order_by(order_clause, User.id.asc())
            .offset(offset)
            .limit(per_page)
        )
        records = self.session.execute(result_stmt).scalars().unique().all()
        return records, total
