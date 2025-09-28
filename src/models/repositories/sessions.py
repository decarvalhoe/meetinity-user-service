"""Repository helpers for ``UserSession`` records."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select

from src.models.user import User, UserSession

from .base import SQLAlchemyRepository, repository_method


class UserSessionRepository(SQLAlchemyRepository):
    """Create and manage user session tokens."""

    @repository_method
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
        self._flush()
        return record

    @repository_method
    def list_sessions(self, user: User) -> list[UserSession]:
        stmt = (
            select(UserSession)
            .where(UserSession.user_id == user.id)
            .order_by(UserSession.created_at.desc(), UserSession.id.desc())
        )
        return self.session.execute(stmt).scalars().all()

    @repository_method
    def get_session_by_id(self, session_id: int) -> Optional[UserSession]:
        return self.session.get(UserSession, session_id)

    @repository_method
    def get_session_by_token(self, token: str) -> Optional[UserSession]:
        stmt = select(UserSession).where(UserSession.session_token == token)
        return self.session.execute(stmt).scalar_one_or_none()

    @repository_method
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
        self._flush()
        return session_record


__all__ = ["UserSessionRepository"]
