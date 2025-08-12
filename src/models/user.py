from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Optional

_USERS: Dict[int, "User"] = {}
_EMAIL_INDEX: Dict[str, int] = {}
_ID_COUNTER = 1


@dataclass
class User:
    id: int
    email: str
    name: Optional[str] = None
    photo_url: Optional[str] = None
    title: Optional[str] = None
    company: Optional[str] = None
    location: Optional[str] = None
    provider: Optional[str] = None
    provider_user_id: Optional[str] = None
    last_login: Optional[datetime] = None
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    updated_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    is_active: bool = True


def upsert_user(email: str, **kwargs) -> User:
    """Create or update a user identified by email."""
    global _ID_COUNTER
    email_key = email.lower()
    if email_key in _EMAIL_INDEX:
        user = _USERS[_EMAIL_INDEX[email_key]]
        for key, value in kwargs.items():
            setattr(user, key, value)
        user.email = email_key
        user.updated_at = datetime.now(timezone.utc)
    else:
        user = User(id=_ID_COUNTER, email=email_key, **kwargs)
        _USERS[_ID_COUNTER] = user
        _EMAIL_INDEX[email_key] = _ID_COUNTER
        _ID_COUNTER += 1
    return user


def get_user_by_email(email: str) -> Optional[User]:
    uid = _EMAIL_INDEX.get(email.lower())
    return _USERS.get(uid) if uid else None


def get_user(user_id: int) -> Optional[User]:
    return _USERS.get(user_id)


def reset_storage():
    """Reset in-memory storage (for tests)."""
    global _USERS, _EMAIL_INDEX, _ID_COUNTER
    _USERS = {}
    _EMAIL_INDEX = {}
    _ID_COUNTER = 1
