"""Base classes for SQLAlchemy repositories with consistent error handling."""

from __future__ import annotations

import logging
from contextlib import contextmanager
from dataclasses import dataclass
from functools import wraps
from typing import Any, Callable, Iterator, TypeVar

from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass(slots=True)
class RepositoryError(Exception):
    """Domain specific wrapper for database errors raised by repositories."""

    message: str
    status_code: int = 500
    details: dict[str, Any] | None = None

    def __str__(self) -> str:  # pragma: no cover - uses dataclass repr
        return self.message


class SQLAlchemyRepository:
    """Base class for repositories using SQLAlchemy sessions."""

    def __init__(self, session: Session) -> None:
        self.session = session

    # ------------------------------------------------------------------
    # Error handling helpers
    # ------------------------------------------------------------------
    def _handle_error(self, exc: SQLAlchemyError) -> None:
        """Rollback the current transaction and raise a ``RepositoryError``."""

        try:
            self.session.rollback()
        except Exception:  # pragma: no cover - log only
            logger.exception("Failed to rollback session after error")
        if isinstance(exc, IntegrityError):
            raise RepositoryError(
                "database integrity error", status_code=409
            ) from exc
        raise RepositoryError("database operation failed") from exc

    def _flush(self) -> None:
        """Flush pending changes with consistent error handling."""

        try:
            self.session.flush()
        except SQLAlchemyError as exc:  # pragma: no cover
            self._handle_error(exc)

    def _execute(self, operation: Callable[[], T]) -> T:
        """Execute ``operation`` catching SQLAlchemy failures."""

        try:
            return operation()
        except SQLAlchemyError as exc:  # pragma: no cover
            self._handle_error(exc)
            raise RepositoryError("database operation failed") from exc

    @contextmanager
    def _wrap(self) -> Iterator[None]:
        """Context manager capturing SQLAlchemy errors inside the block."""

        try:
            yield
        except SQLAlchemyError as exc:  # pragma: no cover
            self._handle_error(exc)
            raise RepositoryError("database operation failed") from exc


def repository_method(func: Callable[..., T]) -> Callable[..., T]:
    """Wrap repository methods with rollback-aware error handling."""

    @wraps(func)
    def wrapper(self: SQLAlchemyRepository, *args: Any, **kwargs: Any) -> T:
        try:
            return func(self, *args, **kwargs)
        except SQLAlchemyError as exc:  # pragma: no cover
            self._handle_error(exc)
            raise RepositoryError("database operation failed") from exc
    return wrapper


__all__ = ["SQLAlchemyRepository", "RepositoryError", "repository_method"]
