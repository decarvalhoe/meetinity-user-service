"""Transactional unit of work helpers built on top of SQLAlchemy sessions."""

from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Iterator

from sqlalchemy.exc import ResourceClosedError
from sqlalchemy.orm import Session

from src.db.session import get_session

logger = logging.getLogger(__name__)

_active_session: ContextVar[Session | None] = ContextVar(
    "transaction_session", default=None
)
_transaction_depth: ContextVar[int] = ContextVar(
    "transaction_depth", default=0
)


class TransactionManager:
    """Coordinate transactional scopes with support for nesting."""

    def __init__(self, session_factory=get_session) -> None:
        self._session_factory = session_factory

    @contextmanager
    def transaction(self, *, name: str = "transaction") -> Iterator[Session]:
        parent = _active_session.get()
        if parent is None:
            session = self._session_factory()
            token = _active_session.set(session)
            depth_token = _transaction_depth.set(1)
            start = time.perf_counter()
            logger.debug("transaction.start name=%s depth=1", name)
            try:
                yield session
                session.commit()
                duration = (time.perf_counter() - start) * 1000
                logger.debug(
                    "transaction.commit name=%s depth=1 duration_ms=%.2f",
                    name,
                    duration,
                )
            except Exception:
                duration = (time.perf_counter() - start) * 1000
                logger.exception(
                    "transaction.rollback name=%s depth=1 duration_ms=%.2f",
                    name,
                    duration,
                )
                session.rollback()
                raise
            finally:
                session.close()
                _active_session.reset(token)
                _transaction_depth.reset(depth_token)
        else:
            depth = _transaction_depth.get()
            nested = parent.begin_nested()
            depth_token = _transaction_depth.set(depth + 1)
            start = time.perf_counter()
            logger.debug(
                "transaction.start name=%s depth=%s nested=True",
                name,
                depth + 1,
            )
            try:
                yield parent
                nested.commit()
                duration = (time.perf_counter() - start) * 1000
                logger.debug(
                    "transaction.commit name=%s depth=%s duration_ms=%.2f "
                    "nested=True",
                    name,
                    depth + 1,
                    duration,
                )
            except Exception:
                duration = (time.perf_counter() - start) * 1000
                logger.exception(
                    "transaction.rollback name=%s depth=%s duration_ms=%.2f "
                    "nested=True",
                    name,
                    depth + 1,
                    duration,
                )
                try:
                    if nested.is_active:
                        nested.rollback()
                except ResourceClosedError:  # pragma: no cover
                    pass
                raise
            finally:
                _transaction_depth.reset(depth_token)


transaction_manager = TransactionManager()


@contextmanager
def transactional_session(*, name: str = "transaction") -> Iterator[Session]:
    """Shortcut to open a transactional scope with instrumentation."""

    with transaction_manager.transaction(name=name) as session:
        yield session


__all__ = [
    "transaction_manager",
    "transactional_session",
    "TransactionManager",
]
