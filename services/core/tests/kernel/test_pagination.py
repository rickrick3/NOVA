import pytest

from nova_core.kernel.pagination import InvalidCursorError, decode_cursor, encode_cursor


def test_cursor_roundtrip():
    assert decode_cursor(encode_cursor(["2026-10-09T12:00:00+00:00", 42]), arity=2) == [
        "2026-10-09T12:00:00+00:00",
        42,
    ]


@pytest.mark.parametrize("cursor", ["", "not-a-cursor", "e30=", "W10="])
def test_tampered_cursor_is_a_validation_error(cursor):
    with pytest.raises(InvalidCursorError) as exc:
        decode_cursor(cursor, arity=2)
    assert (exc.value.code, exc.value.status) == ("validation_error", 422)
