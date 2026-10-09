import sqlalchemy as sa
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext

import nova_core.all_models  # noqa: F401
from nova_core.kernel.config import Settings
from nova_core.kernel.db import Base
from nova_core.kernel.migrate import downgrade, sync_url, upgrade


def _url(tmp_path) -> str:
    return Settings(_env_file=None, env="test", data_dir=tmp_path).resolved_database_url


def test_upgrade_then_downgrade_leaves_an_empty_schema(tmp_path):
    url = _url(tmp_path)
    upgrade(url)
    downgrade(url, "base")
    tables = sa.inspect(sa.create_engine(sync_url(url))).get_table_names()
    assert set(tables) <= {"alembic_version"}


def test_upgrade_is_idempotent_on_an_existing_database(tmp_path):
    url = _url(tmp_path)
    upgrade(url)
    upgrade(url)


def test_models_match_migrations(tmp_path):
    url = _url(tmp_path)
    upgrade(url)
    with sa.create_engine(sync_url(url)).connect() as conn:
        assert compare_metadata(MigrationContext.configure(conn), Base.metadata) == []
