"""Canonical planning fingerprints without MCP package coupling."""

import hashlib
import json


def planning_fingerprint(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), default=str, allow_nan=False
        ).encode()
    ).hexdigest()
