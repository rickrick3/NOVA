import uvicorn

from nova_core.app import create_app
from nova_core.kernel.config import Settings
from nova_core.kernel.logging import configure_logging


def main() -> None:
    settings = Settings()
    configure_logging()
    # access_log=False: RequestContextMiddleware already writes one line per request.
    uvicorn.run(
        create_app(settings),
        host=settings.host,
        port=settings.port,
        log_config=None,
        access_log=False,
    )


if __name__ == "__main__":
    main()
