"""Alembic environment configuration."""

from __future__ import annotations

from logging.config import fileConfig

from sqlalchemy.engine import URL, make_url

from alembic import context

from src.config import get_config
from src.db.session import Base, get_engine


config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

app_config = get_config()
config.set_main_option("sqlalchemy.url", app_config.database_url)

target_metadata = Base.metadata


def _should_render_batch(database_url: str | URL) -> bool:
    url = make_url(database_url)
    return url.get_backend_name() == "sqlite"


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""

    database_url = app_config.database_url
    context.configure(
        url=database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=_should_render_batch(database_url),
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""

    connectable = get_engine()

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=_should_render_batch(str(connection.engine.url)),
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
