"""Deterministic canonical-state fingerprints."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def fingerprint_payload(payload: dict[str, Any]) -> str:
    canonical = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()
