"""SQLAlchemy engine and session management."""

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Any, Iterator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.engine.url import make_url
from sqlalchemy.orm import (
    DeclarativeBase,
    Session,
    close_all_sessions,
    sessionmaker,
)
from sqlalchemy.pool import StaticPool
from sqlalchemy.exc import SQLAlchemyError

from src.config import get_config


class Base(DeclarativeBase):
    """Base class for SQLAlchemy models."""


_engine: Engine | None = None
_SessionFactory: sessionmaker[Session] | None = None

logger = logging.getLogger(__name__)


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
        database_url = config.database_url
        if url.get_backend_name() == "sqlite":
            connect_args = {"check_same_thread": False}
            if url.database in (None, "", ":memory:"):
                engine_kwargs["poolclass"] = StaticPool
            engine_kwargs["connect_args"] = connect_args
        elif (
            url.get_backend_name() == "postgresql"
            and url.get_driver_name() == "psycopg"
        ):
            engine_kwargs.update(
                {
                    "pool_size": config.pool_size,
                    "max_overflow": config.max_overflow,
                    "pool_timeout": config.pool_timeout,
                    "pool_recycle": config.pool_recycle,
                }
            )
            connect_args: dict[str, Any] = {}
            if config.database_ssl_mode:
                connect_args["sslmode"] = config.database_ssl_mode
            if url.query:
                for key, value in url.query.items():
                    connect_args.setdefault(key, value)
            if connect_args:
                engine_kwargs["connect_args"] = connect_args
                database_url = url.set(query={})
        safe_url = url.render_as_string(hide_password=True)
        try:
            _engine = create_engine(database_url, **engine_kwargs)
            with _engine.connect() as connection:
                # Establish a connection early to surface configuration issues.
                if url.get_backend_name() == "postgresql":
                    connection.execute(text("SELECT 1"))
        except SQLAlchemyError:
            logger.exception(
                "Failed to initialize database engine for %s", safe_url
            )
            raise
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
def session_scope(*, name: str = "session") -> Iterator[Session]:
    """Provide a transactional scope around a series of operations."""

    from src.services.transactions import transactional_session

    with transactional_session(name=name) as session:
        yield session


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
