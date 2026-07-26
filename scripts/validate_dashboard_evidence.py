"""Validate a Module 15 snapshot and all mandatory sources."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.dashboard.evidence import validate_snapshot
from src.dashboard.models import EvidenceSnapshot

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--snapshot", type=Path, default=ROOT / "outputs/module15/evidence_snapshot.json"
    )
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    snapshot = EvidenceSnapshot.model_validate_json(args.snapshot.read_text(encoding="utf-8"))
    errors = validate_snapshot(ROOT, snapshot)
    result = {
        "schema_version": 1,
        "status": "PASS" if not errors else "FAIL",
        "evidence_status": "CURRENT" if not errors else "STALE_SOURCE_CHANGED",
        "errors": errors,
        "source_count": len(snapshot.sources),
        "value_count": len(snapshot.values),
        "snapshot_fingerprint": snapshot.snapshot_fingerprint,
    }
    print(json.dumps(result, indent=2 if args.pretty or args.json else None))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
