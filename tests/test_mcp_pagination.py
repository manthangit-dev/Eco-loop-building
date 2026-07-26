import pytest
from src.mcp_server.pagination import decode_cursor, encode_cursor


def test_cursor_round_trip_and_scope() -> None:
    cursor = encode_cursor("tool", "run", 20)
    assert decode_cursor(cursor, "tool", "run") == 20
    with pytest.raises(ValueError):
        decode_cursor(cursor, "other", "run")
    with pytest.raises(ValueError):
        decode_cursor("bad", "tool", "run")
