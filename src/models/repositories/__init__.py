"""Aggregate repositories for user related persistence logic."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, Iterable

from flask import current_app, has_app_context

from src.config import get_config
from src.utils.encryption import ApplicationEncryptor

from sqlalchemy.orm import Session

from .activity import UserActivityRepository
from .base import RepositoryError
from .connections import UserConnectionRepository
from .preferences import UserPreferenceRepository
from .sessions import UserSessionRepository
from .users import UserCoreRepository
from .verifications import UserVerificationRepository

if TYPE_CHECKING:  # pragma: no cover - typing helper
    from src.services.cache import CacheHooks


class UserRepository:
    """Facade exposing all user related repository methods."""

    def __init__(
        self,
        session: Session,
        *,
        cache_hooks: "CacheHooks | None" = None,
        encryptor: "ApplicationEncryptor | None" = None,
    ) -> None:
        if encryptor is None:
            if has_app_context():
                encryptor = current_app.extensions.get("encryptor")
            if encryptor is None:
                config = get_config()
                if config.encryption_primary_key:
                    encryptor = ApplicationEncryptor.from_keys(
                        primary_key=config.encryption_primary_key,
                        fallback_keys=config.encryption_fallback_keys,
                        rotation_days=config.encryption_rotation_days,
                    )
        self.session = session
        self._encryptor = encryptor
        self._repositories: Iterable[object] = (
            UserCoreRepository(
                session, cache_hooks=cache_hooks, encryptor=encryptor
            ),
            UserPreferenceRepository(
                session, cache_hooks=cache_hooks, encryptor=encryptor
            ),
            UserActivityRepository(
                session, cache_hooks=cache_hooks, encryptor=encryptor
            ),
            UserConnectionRepository(
                session, cache_hooks=cache_hooks, encryptor=encryptor
            ),
            UserSessionRepository(
                session, cache_hooks=cache_hooks, encryptor=encryptor
            ),
            UserVerificationRepository(
                session, cache_hooks=cache_hooks, encryptor=encryptor
            ),
        )

    def __getattr__(self, name: str) -> Any:
        for repository in self._repositories:
            if hasattr(repository, name):
                return getattr(repository, name)
        raise AttributeError(name)

    def __dir__(self) -> list[str]:  # pragma: no cover - convenience only
        names = set(super().__dir__())
        for repository in self._repositories:
            names.update(
                attr for attr in dir(repository) if not attr.startswith("_")
            )
        return sorted(names)


def _make_delegate(name: str) -> Callable[..., Any]:
    def _delegate(self: UserRepository, *args: Any, **kwargs: Any) -> Any:
        for repository in self._repositories:
            if hasattr(repository, name):
                return getattr(repository, name)(*args, **kwargs)
        raise AttributeError(name)

    _delegate.__name__ = name
    return _delegate


_DELEGATED_REPOSITORIES = (
    UserCoreRepository,
    UserPreferenceRepository,
    UserActivityRepository,
    UserConnectionRepository,
    UserSessionRepository,
    UserVerificationRepository,
)

for _repository in _DELEGATED_REPOSITORIES:
    for _attr_name, _attr in _repository.__dict__.items():
        if _attr_name.startswith("_"):
            continue
        if not callable(_attr):
            continue
        if hasattr(UserRepository, _attr_name):
            continue
        setattr(UserRepository, _attr_name, _make_delegate(_attr_name))


__all__ = [
    "RepositoryError",
    "UserRepository",
    "UserActivityRepository",
    "UserPreferenceRepository",
    "UserConnectionRepository",
    "UserSessionRepository",
    "UserVerificationRepository",
    "UserCoreRepository",
]
