"""Alembic environment. Uses a synchronous engine; see nova_core.kernel.migrate.

Logging is deliberately left alone: alembic's usual fileConfig() call would disable the
application's own loggers.
"""

from alembic import context
from sqlalchemy import create_engine, pool

import nova_core.all_models  # noqa: F401 - registers every model on Base.metadata
from nova_core.kernel.db import Base

config = context.config
target_metadata = Base.metadata


def _database_url() -> str:
    # The application passes the URL through nova_core.kernel.migrate. From the command
    # line it must be given explicitly: guessing would point `alembic downgrade` at the
    # user's real database.
    url = (
        config.attributes.get("database_url")
        or context.get_x_argument(as_dictionary=True).get("database_url")
        or config.get_main_option("sqlalchemy.url")
    )
    if not url:
        raise RuntimeError(
            "no database URL: pass one explicitly, for example "
            "`alembic -x database_url=sqlite:///path/to/nova.db upgrade head`"
        )
    return str(url)


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
    # hide_parameters: a failing statement must not put row values in the log.
    engine = create_engine(_database_url(), poolclass=pool.NullPool, hide_parameters=True)
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
