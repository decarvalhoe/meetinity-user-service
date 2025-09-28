"""Persistence helpers for audit logs."""

from __future__ import annotations

from typing import Any, Optional

from src.models.audit import AuditLog

from .base import SQLAlchemyRepository, repository_method


class AuditLogRepository(SQLAlchemyRepository):
    """Create immutable audit log entries."""

    @repository_method
    def record_event(
        self,
        *,
        event: str,
        user_id: Optional[int] = None,
        actor: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ) -> AuditLog:
        entry = AuditLog(
            event=event,
            user_id=user_id,
            actor=actor,
            ip_address=ip_address,
            user_agent=user_agent,
            details=details or {},
        )
        self.session.add(entry)
        self._flush()
        return entry


__all__ = ["AuditLogRepository"]
