"""Runs Alembic migrations. Synchronous on purpose: callers inside an event loop
use ``asyncio.to_thread``."""

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy.engine import make_url

# src/nova_core/kernel/migrate.py -> services/core/migrations
MIGRATIONS_DIR = Path(__file__).resolve().parents[3] / "migrations"

_ASYNC_SQLITE = "sqlite+aiosqlite:"


def sync_url(database_url: str) -> str:
    if database_url.startswith(_ASYNC_SQLITE):
        return "sqlite:" + database_url[len(_ASYNC_SQLITE) :]
    return database_url


def _config(database_url: str) -> Config:
    config = Config()
    # set_main_option goes through ConfigParser interpolation, hence the escaped "%".
    config.set_main_option("script_location", str(MIGRATIONS_DIR).replace("%", "%%"))
    config.attributes["database_url"] = sync_url(database_url)
    return config


def _ensure_sqlite_parent(database_url: str) -> None:
    url = make_url(sync_url(database_url))
    if url.get_backend_name() == "sqlite" and url.database and url.database != ":memory:":
        Path(url.database).parent.mkdir(parents=True, exist_ok=True)


def upgrade(database_url: str, revision: str = "head") -> None:
    _ensure_sqlite_parent(database_url)
    command.upgrade(_config(database_url), revision)


def downgrade(database_url: str, revision: str) -> None:
    _ensure_sqlite_parent(database_url)
    command.downgrade(_config(database_url), revision)
