"""Stable tool/run-bound pagination cursors."""

import base64
import json


def encode_cursor(tool: str, run_id: str | None, offset: int) -> str:
    payload = json.dumps(
        {"offset": offset, "run_id": run_id, "tool": tool}, sort_keys=True, separators=(",", ":")
    )
    return base64.urlsafe_b64encode(payload.encode()).decode().rstrip("=")


def decode_cursor(cursor: str, tool: str, run_id: str | None) -> int:
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded).decode())
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("invalid cursor") from exc
    if payload != {"offset": payload.get("offset"), "run_id": run_id, "tool": tool}:
        raise ValueError("cursor belongs to another tool or run")
    offset = payload["offset"]
    if type(offset) is not int or offset < 0:
        raise ValueError("invalid cursor offset")
    return offset
