"""Cursor pagination shared by every listing."""

import base64
import binascii
import json
from collections.abc import Sequence
from dataclasses import dataclass

from nova_core.kernel.errors import NovaError

# Real cursors are a few dozen characters; anything long is not one of ours.
MAX_CURSOR_LENGTH = 512


@dataclass(frozen=True)
class Page[T]:
    items: list[T]
    next_cursor: str | None


class InvalidCursorError(NovaError):
    def __init__(self) -> None:
        super().__init__("validation_error", 422, "The pagination cursor is invalid.")


def encode_cursor(values: Sequence[str | int]) -> str:
    raw = json.dumps(list(values), separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode_cursor(cursor: str, arity: int) -> list[str | int]:
    """Decodes a cursor produced by ``encode_cursor``. A cursor comes from the client,
    so anything unexpected is a validation error, never a crash."""
    if len(cursor) > MAX_CURSOR_LENGTH:
        raise InvalidCursorError()
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        value = json.loads(base64.b64decode(padded, altchars=b"-_", validate=True))
    except (ValueError, binascii.Error, RecursionError):
        raise InvalidCursorError() from None
    if not isinstance(value, list) or len(value) != arity:
        raise InvalidCursorError()
    if any(isinstance(item, bool) or not isinstance(item, (str, int)) for item in value):
        raise InvalidCursorError()
    return value
