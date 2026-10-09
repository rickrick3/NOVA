import pytest
from pydantic import ValidationError

from nova_core.kernel.config import Settings


def test_local_env_refuses_non_loopback_host(tmp_path):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, env="local", host="0.0.0.0", data_dir=tmp_path)


def test_hosted_env_accepts_any_host(tmp_path):
    assert (
        Settings(_env_file=None, env="hosted", host="0.0.0.0", data_dir=tmp_path).host == "0.0.0.0"
    )


def test_allowed_hosts_and_origins_cover_core_and_studio_dev_ports(tmp_path):
    s = Settings(_env_file=None, env="test", data_dir=tmp_path)
    assert s.allowed_hosts == {
        "127.0.0.1:8000",
        "localhost:8000",
        "127.0.0.1:5173",
        "localhost:5173",
    }
    assert s.allowed_origins == {
        "http://127.0.0.1:8000",
        "http://localhost:8000",
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    }


def test_database_defaults_to_a_file_in_the_data_dir(tmp_path):
    s = Settings(_env_file=None, env="test", data_dir=tmp_path)
    assert s.resolved_database_url.startswith("sqlite+aiosqlite:///")
    assert s.resolved_database_url.endswith("nova.db")
