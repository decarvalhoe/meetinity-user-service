"""Repository helpers for extended user connections."""

from __future__ import annotations

from typing import Optional

from sqlalchemy import select

from src.models.user import User, UserConnection

from .base import SQLAlchemyRepository, repository_method


class UserConnectionRepository(SQLAlchemyRepository):
    """Manage ``UserConnection`` aggregates."""

    @repository_method
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
        self._flush()
        self._invalidate_profile_cache(user.id)
        return connection

    @repository_method
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
        self._flush()
        self._invalidate_profile_cache(connection.user_id)
        return connection

    @repository_method
    def delete_connection(self, connection: UserConnection) -> None:
        user_id = connection.user_id
        self.session.delete(connection)
        self._flush()
        self._invalidate_profile_cache(user_id)

    @repository_method
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

    @repository_method
    def get_connection_by_id(
        self, connection_id: int
    ) -> Optional[UserConnection]:
        return self.session.get(UserConnection, connection_id)


__all__ = ["UserConnectionRepository"]
