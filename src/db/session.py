"""SQLAlchemy engine and session management."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.engine.url import make_url
from sqlalchemy.orm import (
    DeclarativeBase,
    Session,
    close_all_sessions,
    sessionmaker,
)
from sqlalchemy.pool import StaticPool

from src.config import get_config


class Base(DeclarativeBase):
    """Base class for SQLAlchemy models."""


_engine: Engine | None = None
_SessionFactory: sessionmaker[Session] | None = None


def get_engine() -> Engine:
    """Return a configured SQLAlchemy engine."""

    global _engine
    if _engine is None:
        config = get_config()
        url = make_url(config.database_url)
        engine_kwargs: dict[str, object] = {
            "echo": config.sqlalchemy_echo,
            "pool_pre_ping": True,
            "future": True,
        }
        if url.get_backend_name() == "sqlite":
            connect_args = {"check_same_thread": False}
            if url.database in (None, "", ":memory:"):
                engine_kwargs["poolclass"] = StaticPool
            engine_kwargs["connect_args"] = connect_args
        _engine = create_engine(config.database_url, **engine_kwargs)
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    """Return the configured session factory."""

    global _SessionFactory
    if _SessionFactory is None:
        _SessionFactory = sessionmaker(
            bind=get_engine(),
            autocommit=False,
            autoflush=False,
            expire_on_commit=False,
            future=True,
        )
    return _SessionFactory


def get_session() -> Session:
    """Create a new SQLAlchemy session."""

    return get_session_factory()()


@contextmanager
def session_scope() -> Iterator[Session]:
    """Provide a transactional scope around a series of operations."""

    session = get_session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def reset_engine() -> None:
    """Dispose of the engine and reset the session factory (used in tests)."""

    global _engine, _SessionFactory
    if _SessionFactory is not None:
        close_all_sessions()
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _SessionFactory = None
    get_config.cache_clear()
