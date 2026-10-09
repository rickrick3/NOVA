"""Request identifier, request log line and JSON log formatting."""

import json
import logging
import re
import time
from typing import Any

from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from nova_core.kernel.errors import REQUEST_ID_HEADER, problem
from nova_core.kernel.ids import new_id

_REQUEST_ID = re.compile(r"[A-Za-z0-9-]{1,64}")
_request_logger = logging.getLogger("nova_core.request")
_error_logger = logging.getLogger("nova_core.error")

# Attributes every LogRecord carries; anything else was passed through ``extra``.
_STANDARD_ATTRIBUTES = frozenset(logging.makeLogRecord({}).__dict__) | {"message", "asctime"}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry: dict[str, Any] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key not in _STANDARD_ATTRIBUTES:
                entry[key] = value
        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(entry, ensure_ascii=False, default=str)


def configure_logging(level: int = logging.INFO) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level)


class RequestContextMiddleware:
    """Gives each request an identifier, logs it once, and turns crashes into a 500 problem."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        supplied = Headers(scope=scope).get(REQUEST_ID_HEADER, "")
        request_id = supplied if _REQUEST_ID.fullmatch(supplied) else new_id()
        scope.setdefault("state", {})["request_id"] = request_id

        status = 500
        started = False
        began = time.perf_counter()

        async def send_with_request_id(message: Message) -> None:
            nonlocal status, started
            if message["type"] == "http.response.start":
                started = True
                status = message["status"]
                MutableHeaders(scope=message)[REQUEST_ID_HEADER] = request_id
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        except Exception:
            _error_logger.exception("unhandled error", extra={"request_id": request_id})
            if started:
                raise
            response = problem(
                status=500,
                code="internal_error",
                detail="An unexpected error occurred.",
                request_id=request_id,
            )
            await response(scope, receive, send_with_request_id)
        finally:
            _request_logger.info(
                "request",
                extra={
                    "request_id": request_id,
                    "method": scope["method"],
                    "path": scope["path"],
                    "status": status,
                    "duration_ms": round((time.perf_counter() - began) * 1000, 1),
                },
            )
