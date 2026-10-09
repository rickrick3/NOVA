import ipaddress
import os
import sys
from pathlib import Path
from typing import Literal, Self

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_LOCAL_NAMES = ("127.0.0.1", "localhost")


def _default_data_dir() -> Path:
    if sys.platform == "win32":
        local_app_data = os.environ.get("LOCALAPPDATA")
        base = Path(local_app_data) if local_app_data else Path.home() / "AppData" / "Local"
        return base / "NOVA"
    return Path.home() / ".local" / "share" / "nova"


def _is_loopback(host: str) -> bool:
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="NOVA_", env_file=".env", extra="ignore")

    env: Literal["local", "test", "hosted"] = "local"
    host: str = "127.0.0.1"
    port: int = 8000
    studio_dev_port: int = 5173
    data_dir: Path = Field(default_factory=_default_data_dir)
    database_url: str | None = None
    session_cookie_name: str = "nova_session"
    session_ttl_hours: int = 168
    auth_rate_limit_attempts: int = 5
    auth_rate_limit_window_seconds: int = 60
    max_blob_bytes: int = 52_428_800
    # The interactive API page loads scripts from a public CDN: off unless asked for.
    api_docs: bool = False

    @model_validator(mode="after")
    def _local_mode_listens_on_loopback_only(self) -> Self:
        if self.env == "local" and not _is_loopback(self.host):
            raise ValueError("in local mode the Core only listens on a loopback address")
        return self

    @property
    def resolved_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        return f"sqlite+aiosqlite:///{(self.data_dir / 'nova.db').as_posix()}"

    @property
    def allowed_hosts(self) -> frozenset[str]:
        ports = (self.port, self.studio_dev_port)
        return frozenset(f"{name}:{port}" for name in _LOCAL_NAMES for port in ports)

    @property
    def allowed_origins(self) -> frozenset[str]:
        return frozenset(f"http://{host}" for host in self.allowed_hosts)
