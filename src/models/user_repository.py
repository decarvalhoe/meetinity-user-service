"""Repository for user persistence."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable, Optional, Sequence, Tuple

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from src.models.user import (
    User,
    UserActivity,
    UserConnection,
    UserPreference,
    UserSession,
    UserSocialAccount,
    UserVerification,
)
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
            user.active_tokens = self._normalize_tokens(data["active_tokens"])

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
    # Extended aggregates
    # ------------------------------------------------------------------
    def update_privacy(
        self,
        user: User,
        *,
        privacy_settings: Optional[dict[str, object]] = None,
        active_tokens: Optional[Iterable[str]] = None,
    ) -> User:
        """Persist privacy settings and active authentication tokens."""

        if privacy_settings is not None:
            user.privacy_settings = dict(privacy_settings)
        if active_tokens is not None:
            user.active_tokens = self._normalize_tokens(active_tokens)
        self.session.flush()
        return user

    def record_activity(
        self,
        user: User,
        *,
        activity_type: str,
        description: Optional[str] = None,
        score_delta: int = 0,
    ) -> UserActivity:
        """Append a new activity entry for the user."""

        entry = UserActivity(
            user=user,
            activity_type=activity_type,
            description=description,
            score_delta=score_delta,
        )
        if score_delta:
            new_score = (user.engagement_score or 0) + score_delta
            user.engagement_score = max(0, new_score)
        self.session.add(entry)
        self.session.flush()
        return entry

    def list_activities(
        self,
        user: User,
        *,
        limit: int = 50,
    ) -> list[UserActivity]:
        stmt = (
            select(UserActivity)
            .where(UserActivity.user_id == user.id)
            .order_by(UserActivity.created_at.desc(), UserActivity.id.desc())
            .limit(limit)
        )
        return self.session.execute(stmt).scalars().all()

    def create_verification(
        self,
        user: User,
        *,
        method: str,
        code: str,
        expires_at: Optional[datetime] = None,
    ) -> UserVerification:
        existing = self.get_verification(user.id, method)
        if existing:
            existing.code = code
            existing.status = "pending"
            existing.attempts = 0
            existing.expires_at = expires_at
            existing.verified_at = None
            verification = existing
        else:
            verification = UserVerification(
                user=user,
                method=method,
                code=code,
                expires_at=expires_at,
            )
            self.session.add(verification)
        self.session.flush()
        return verification

    def get_verification(
        self, user_id: int, method: str
    ) -> Optional[UserVerification]:
        stmt = (
            select(UserVerification)
            .where(
                UserVerification.user_id == user_id,
                UserVerification.method == method,
            )
        )
        return self.session.execute(stmt).scalar_one_or_none()

    def get_verification_by_id(
        self, verification_id: int
    ) -> Optional[UserVerification]:
        return self.session.get(UserVerification, verification_id)

    def confirm_verification(
        self,
        verification: UserVerification,
        *,
        provided_code: str,
        at: Optional[datetime] = None,
    ) -> bool:
        if at is not None:
            now = at
        else:
            now = datetime.now(timezone.utc)
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        verification.attempts = (verification.attempts or 0) + 1
        expires_at = verification.expires_at
        if expires_at is not None and expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at and now > expires_at:
            verification.status = "expired"
            self.session.flush()
            return False
        if verification.code != provided_code:
            verification.status = "pending"
            self.session.flush()
            return False
        verification.status = "verified"
        verification.verified_at = now
        self.session.flush()
        return True

    def create_connection(
        self,
        user: User,
        *,
        connection_type: str,
        status: str = "pending",
        target_user_id: Optional[int] = None,
        external_reference: Optional[str] = None,
        attributes: Optional[dict[str, object]] = None,
    ) -> UserConnection:
        connection = UserConnection(
            user=user,
            connection_type=connection_type,
            status=status,
            target_user_id=target_user_id,
            external_reference=external_reference,
            attributes=attributes,
        )
        self.session.add(connection)
        self.session.flush()
        return connection

    def update_connection_status(
        self,
        connection: UserConnection,
        *,
        status: str,
        attributes: Optional[dict[str, object]] = None,
    ) -> UserConnection:
        connection.status = status
        if attributes is not None:
            connection.attributes = attributes
        self.session.flush()
        return connection

    def delete_connection(self, connection: UserConnection) -> None:
        self.session.delete(connection)
        self.session.flush()

    def list_connections(
        self,
        user: User,
        *,
        status: Optional[str] = None,
    ) -> list[UserConnection]:
        stmt = select(UserConnection).where(UserConnection.user_id == user.id)
        if status:
            stmt = stmt.where(UserConnection.status == status)
        stmt = stmt.order_by(
            UserConnection.updated_at.desc(),
            UserConnection.id.desc(),
        )
        return self.session.execute(stmt).scalars().all()

    def get_connection_by_id(
        self, connection_id: int
    ) -> Optional[UserConnection]:
        return self.session.get(UserConnection, connection_id)

    def create_session(
        self,
        user: User,
        *,
        session_token: str,
        encrypted_payload: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        expires_at: Optional[datetime] = None,
    ) -> UserSession:
        record = UserSession(
            user=user,
            session_token=session_token,
            encrypted_payload=encrypted_payload,
            ip_address=ip_address,
            user_agent=user_agent,
            expires_at=expires_at,
        )
        self.session.add(record)
        self.session.flush()
        return record

    def list_sessions(self, user: User) -> list[UserSession]:
        stmt = (
            select(UserSession)
            .where(UserSession.user_id == user.id)
            .order_by(UserSession.created_at.desc(), UserSession.id.desc())
        )
        return self.session.execute(stmt).scalars().all()

    def get_session_by_id(self, session_id: int) -> Optional[UserSession]:
        return self.session.get(UserSession, session_id)

    def get_session_by_token(self, token: str) -> Optional[UserSession]:
        stmt = select(UserSession).where(UserSession.session_token == token)
        return self.session.execute(stmt).scalar_one_or_none()

    def revoke_session(
        self,
        session_record: UserSession,
        *,
        revoked_at: Optional[datetime] = None,
    ) -> UserSession:
        if revoked_at is None:
            revoked_at = datetime.now(timezone.utc)
        elif revoked_at.tzinfo is None:
            revoked_at = revoked_at.replace(tzinfo=timezone.utc)
        session_record.revoked_at = revoked_at
        self.session.flush()
        return session_record

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

    @staticmethod
    def _normalize_tokens(tokens: Iterable[str]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for token in tokens:
            token_str = str(token).strip()
            if not token_str or token_str in seen:
                continue
            seen.add(token_str)
            normalized.append(token_str)
        return normalized
