"""Alembic environment. Uses a synchronous engine; see nova_core.kernel.migrate.

Logging is deliberately left alone: alembic's usual fileConfig() call would disable the
application's own loggers.
"""

from alembic import context
from sqlalchemy import create_engine, pool

import nova_core.all_models  # noqa: F401 - registers every model on Base.metadata
from nova_core.kernel.config import Settings
from nova_core.kernel.db import Base
from nova_core.kernel.migrate import sync_url

config = context.config
target_metadata = Base.metadata


def _database_url() -> str:
    configured = config.attributes.get("database_url") or config.get_main_option("sqlalchemy.url")
    # Command-line use (alembic revision, alembic upgrade) falls back to the app settings.
    return configured or sync_url(Settings().resolved_database_url)


def run_migrations_offline() -> None:
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        render_as_batch=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(_database_url(), poolclass=pool.NullPool)
    try:
        with engine.connect() as connection:
            context.configure(
                connection=connection,
                target_metadata=target_metadata,
                render_as_batch=connection.dialect.name == "sqlite",
            )
            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
