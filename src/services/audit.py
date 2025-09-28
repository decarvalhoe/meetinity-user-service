"""Utilities for recording persistent audit trail entries."""

from __future__ import annotations

from typing import Optional

from flask import has_request_context, request

from src.models.repositories.audit import AuditLogRepository
from src.services.transactions import transactional_session


def log_audit_event(
    event: str,
    *,
    session=None,
    user_id: Optional[int] = None,
    actor: Optional[str] = None,
    details: Optional[dict[str, object]] = None,
) -> None:
    """Persist a security-relevant event for traceability."""

    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    if has_request_context():
        forwarded = request.headers.get("X-Forwarded-For")
        ip_address = (forwarded or request.remote_addr or "")
        ip_address = ip_address.split(",")[0].strip()
        user_agent = request.headers.get("User-Agent")

    payload = {
        "event": event,
        "user_id": user_id,
        "actor": actor,
        "ip_address": ip_address or None,
        "user_agent": user_agent or None,
        "details": details or {},
    }

    if session is not None:
        AuditLogRepository(session).record_event(**payload)
        return

    with transactional_session(name=f"audit.{event}") as audit_session:
        AuditLogRepository(audit_session).record_event(**payload)


__all__ = ["log_audit_event"]
