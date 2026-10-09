from datetime import UTC, datetime, timedelta, timezone

import httpx
import pytest
from sqlalchemy import text

from nova_core.app import create_app
from nova_core.kernel.config import Settings
from nova_core.kernel.db import UTCDateTime
from tests.support import BASE_URL


def test_utc_datetime_rejects_naive_values():
    with pytest.raises(ValueError):
        UTCDateTime().process_bind_param(datetime(2026, 10, 9, 12, 0), None)


def test_utc_datetime_converts_other_zones_to_utc():
    paris = datetime(2026, 10, 9, 14, 0, tzinfo=timezone(timedelta(hours=2)))
    stored = UTCDateTime().process_bind_param(paris, None)
    assert (stored.hour, stored.utcoffset()) == (12, timedelta(0))


def test_utc_datetime_returns_aware_values_from_naive_storage():
    loaded = UTCDateTime().process_result_value(datetime(2026, 10, 9, 12, 0), None)
    assert loaded == datetime(2026, 10, 9, 12, 0, tzinfo=UTC)


async def test_sqlite_enforces_foreign_keys(session):
    assert (await session.execute(text("PRAGMA foreign_keys"))).scalar_one() == 1


async def test_health_reports_the_database(client):
    assert (await client.get("/api/v1/system/health")).json()["database"] == "ok"


async def test_health_is_503_when_the_database_is_unreachable(client, monkeypatch):
    async def failing(engine) -> None:
        raise OSError("disk gone")

    monkeypatch.setattr("nova_core.kernel.db.ping_database", failing)
    r = await client.get("/api/v1/system/health")
    assert r.status_code == 503
    assert (r.json()["status"], r.json()["database"]) == ("degraded", "error")


async def test_core_starts_in_a_data_dir_with_spaces_and_accents(tmp_path):
    settings = Settings(_env_file=None, env="test", data_dir=tmp_path / "Mes données NOVA")
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url=BASE_URL
        ) as c:
            assert (await c.get("/api/v1/system/health")).json()["database"] == "ok"
    assert (settings.data_dir / "nova.db").is_file()
