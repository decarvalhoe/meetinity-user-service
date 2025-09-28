"""Repository dedicated to user activity entries."""

from __future__ import annotations

from typing import Optional

from sqlalchemy import select

from src.models.user import User, UserActivity

from .base import SQLAlchemyRepository, repository_method


class UserActivityRepository(SQLAlchemyRepository):
    """Persist and retrieve ``UserActivity`` records."""

    @repository_method
    def record_activity(
        self,
        user: User,
        *,
        activity_type: str,
        description: Optional[str] = None,
        score_delta: int = 0,
    ) -> UserActivity:
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
        self._flush()
        return entry

    @repository_method
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


__all__ = ["UserActivityRepository"]
