"""Nothing sensitive in database errors; the pinned contract describes the real error bodies."""

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text

from nova_core.kernel.migrate import MIGRATIONS_DIR


async def test_database_errors_do_not_carry_bound_values(app):
    async with app.state.engine.connect() as connection:
        with pytest.raises(Exception) as failure:  # noqa: B017, PT011 - any driver error
            await connection.execute(
                text("INSERT INTO no_such_table (v) VALUES (:v)"), {"v": "s3cr3t-token-value"}
            )
    assert "s3cr3t-token-value" not in str(failure.value)


def test_command_line_migrations_refuse_to_guess_the_database(tmp_path, monkeypatch):
    # If the guess were still there it would land in tmp_path, not in the real data directory.
    monkeypatch.setenv("NOVA_DATA_DIR", str(tmp_path))
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS_DIR).replace("%", "%%"))
    with pytest.raises(RuntimeError, match="database URL"):
        command.upgrade(config, "head")
    assert not (tmp_path / "nova.db").exists()


async def test_error_bodies_are_documented_as_problem_json(app):
    schema = app.openapi()
    components = schema["components"]["schemas"]
    assert "HTTPValidationError" not in components
    assert {"Problem", "ValidationProblem"} <= set(components)
    assert {"code", "status", "detail", "request_id"} <= set(components["Problem"]["properties"])

    for path, operations in schema["paths"].items():
        for method, operation in operations.items():
            responses = operation["responses"]
            where = f"{method.upper()} {path}"
            assert responses["default"]["content"] == {
                "application/problem+json": {"schema": {"$ref": "#/components/schemas/Problem"}}
            }, where
            if "422" in responses:
                assert responses["422"]["content"] == {
                    "application/problem+json": {
                        "schema": {"$ref": "#/components/schemas/ValidationProblem"}
                    }
                }, where
