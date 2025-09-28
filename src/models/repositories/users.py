"""Repositories handling persistence for ``User`` aggregates."""

from __future__ import annotations

from datetime import datetime
from typing import Iterable, Optional, Sequence, Tuple

from sqlalchemy import func, or_, select

from src.models.user import (
    User,
    UserSocialAccount,
)
from src.utils.lists import encode_string_list

from .base import SQLAlchemyRepository, repository_method


SORT_FIELDS = {
    "created_at": User.created_at,
    "updated_at": User.updated_at,
    "last_login": User.last_login,
    "experience_years": User.experience_years,
    "name": User.name,
}


class UserCoreRepository(SQLAlchemyRepository):
    """Core operations for the ``User`` entity."""

    @repository_method
    def get(self, user_id: int) -> Optional[User]:
        return self.session.get(User, user_id)

    @repository_method
    def get_by_email(self, email: str) -> Optional[User]:
        normalized = normalize_email(email)
        stmt = select(User).where(User.email == normalized)
        return self.session.execute(stmt).unique().scalar_one_or_none()

    @repository_method
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
        normalized_email = normalize_email(email)
        validate_email(normalized_email)

        user = self.get_by_email(normalized_email)
        if user is None:
            user = User(email=normalized_email)
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

        sync_social_account(
            user,
            provider=provider,
            provider_user_id=provider_user_id,
            display_name=name,
            profile_url=social_profile_url,
            connected_at=last_login,
        )

        self._flush()
        self._invalidate_profile_cache(user.id)
        self._invalidate_listing_cache()

        return user

    @repository_method
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
        normalized_email = normalize_email(email)
        validate_email(normalized_email)

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
        self._flush()
        self._invalidate_profile_cache(user.id)
        self._invalidate_listing_cache()
        return user

    @repository_method
    def update_user(self, user: User, data: dict[str, object]) -> User:
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
            "engagement_score": "engagement_score",
            "reputation_score": "reputation_score",
        }
        for field, attr in mapping.items():
            if field in data:
                setattr(user, attr, data[field])

        if "skills" in data:
            user.skills = encode_string_list(data.get("skills"))
        if "interests" in data:
            user.interests = encode_string_list(data.get("interests"))
        if "privacy_settings" in data and data["privacy_settings"] is not None:
            user.privacy_settings = dict(data["privacy_settings"])
        if "active_tokens" in data and data["active_tokens"] is not None:
            user.active_tokens = normalize_tokens(data["active_tokens"])

        self._flush()
        self._invalidate_profile_cache(user.id)
        self._invalidate_listing_cache()
        return user

    @repository_method
    def delete_user(self, user: User) -> None:
        self.session.delete(user)
        self._flush()
        self._invalidate_profile_cache(user.id)
        self._invalidate_listing_cache()

    @repository_method
    def set_photo_url(self, user: User, photo_url: str) -> User:
        user.photo_url = photo_url
        self._flush()
        self._invalidate_profile_cache(user.id)
        return user

    @repository_method
    def deactivate(self, user: User) -> None:
        user.is_active = False
        self._flush()
        self._invalidate_profile_cache(user.id)
        self._invalidate_listing_cache()

    @repository_method
    def bulk_import_users(
        self,
        records: Iterable[dict[str, object]],
        *,
        update_existing: bool = True,
    ) -> list[User]:
        prepared: list[tuple[str, dict[str, object]]] = []
        for record in records:
            if "email" not in record:
                raise ValueError("email is required for bulk import")
            normalized_email = normalize_email(str(record["email"]))
            validate_email(normalized_email)
            prepared.append((normalized_email, dict(record)))

        if not prepared:
            return []

        emails = [email for email, _ in prepared]
        existing_records = (
            self.session.execute(select(User).where(User.email.in_(emails)))
            .scalars()
            .unique()
            .all()
        )
        existing = {user.email: user for user in existing_records}

        seen: set[int] = set()
        touched: list[User] = []

        for email, payload in prepared:
            user = existing.get(email)
            if user is None:
                user = User(email=email)
                existing[email] = user
                self.session.add(user)
            elif not update_existing:
                continue

            # Update scalar fields when provided
            for field in (
                "name",
                "title",
                "company",
                "location",
                "industry",
                "linkedin_url",
                "experience_years",
                "bio",
                "timezone",
                "provider",
                "provider_user_id",
            ):
                if field in payload:
                    setattr(user, field, payload[field])

            if "is_active" in payload:
                user.is_active = bool(payload["is_active"])
            if "skills" in payload:
                user.skills = encode_string_list(payload.get("skills"))
            if "interests" in payload:
                user.interests = encode_string_list(payload.get("interests"))
            if (
                "active_tokens" in payload
                and payload["active_tokens"] is not None
            ):
                user.active_tokens = normalize_tokens(payload["active_tokens"])
            if (
                "privacy_settings" in payload
                and payload["privacy_settings"] is not None
            ):
                user.privacy_settings = dict(payload["privacy_settings"])

            for field in ("last_login", "last_active_at", "updated_at"):
                if field in payload and payload[field] is not None:
                    setattr(user, field, payload[field])

            if (
                "engagement_score" in payload
                and payload["engagement_score"] is not None
            ):
                user.engagement_score = int(payload["engagement_score"])
            if (
                "reputation_score" in payload
                and payload["reputation_score"] is not None
            ):
                user.reputation_score = int(payload["reputation_score"])

            marker = id(user)
            if marker not in seen:
                seen.add(marker)
                touched.append(user)

        if not touched:
            return []

        self._flush()
        self._invalidate_listing_cache()
        for user in touched:
            self._invalidate_profile_cache(user.id)
        return touched

    @repository_method
    def list_users(
        self,
        *,
        page: int,
        per_page: int,
        sort: Tuple[str, str],
        filters: dict[str, object],
    ) -> Tuple[list[User], int]:
        stmt = select(User)
        stmt = stmt.where(User.is_active.is_(True))
        stmt = self._apply_filters(stmt, filters)
        return self._paginate(stmt, page, per_page, sort)

    @repository_method
    def search_users(
        self,
        *,
        query: str,
        page: int,
        per_page: int,
        sort: Tuple[str, str],
        filters: dict[str, object],
    ) -> Tuple[list[User], int]:
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

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
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


def normalize_email(email: str) -> str:
    return email.strip().lower()


def validate_email(email: str) -> None:
    if "@" not in email:
        raise ValueError("invalid email address")


def normalize_tokens(tokens: Iterable[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for token in tokens:
        token_str = str(token).strip()
        if not token_str or token_str in seen:
            continue
        seen.add(token_str)
        normalized.append(token_str)
    return normalized


def sync_social_account(
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


__all__ = [
    "UserCoreRepository",
    "normalize_email",
    "validate_email",
    "normalize_tokens",
    "sync_social_account",
    "SORT_FIELDS",
]
