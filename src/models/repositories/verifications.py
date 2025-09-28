"""Repository utilities for ``UserVerification`` records."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select

from src.models.user import User, UserVerification

from .base import SQLAlchemyRepository, repository_method


class UserVerificationRepository(SQLAlchemyRepository):
    """Create and manage verification challenges."""

    @repository_method
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
        self._flush()
        self._invalidate_profile_cache(user.id)
        return verification

    @repository_method
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

    @repository_method
    def get_verification_by_id(
        self, verification_id: int
    ) -> Optional[UserVerification]:
        return self.session.get(UserVerification, verification_id)

    @repository_method
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
            self._flush()
            self._invalidate_profile_cache(verification.user_id)
            return False
        if verification.code != provided_code:
            verification.status = "pending"
            self._flush()
            self._invalidate_profile_cache(verification.user_id)
            return False
        verification.status = "verified"
        verification.verified_at = now
        self._flush()
        self._invalidate_profile_cache(verification.user_id)
        return True


__all__ = ["UserVerificationRepository"]
