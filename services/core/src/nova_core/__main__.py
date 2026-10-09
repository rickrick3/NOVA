from typing import Any

import uvicorn

from nova_core.app import create_app
from nova_core.kernel.config import Settings
from nova_core.kernel.logging import configure_logging


def server_options(settings: Settings) -> dict[str, Any]:
    """The uvicorn options the Core really runs with; kept in one place so tests can use them."""
    return {
        "host": settings.host,
        "port": settings.port,
        "log_config": None,
        # RequestContextMiddleware already writes one line per request.
        "access_log": False,
        # The Core is not behind a proxy. With proxy headers on, uvicorn would let any
        # local client name its own address through X-Forwarded-For and so pick its own
        # rate-limit bucket.
        "proxy_headers": False,
    }


def main() -> None:
    settings = Settings()
    configure_logging()
    uvicorn.run(create_app(settings), **server_options(settings))


if __name__ == "__main__":
    main()
