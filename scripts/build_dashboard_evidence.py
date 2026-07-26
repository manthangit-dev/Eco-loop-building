"""Build or validate the bounded Module 15 evidence snapshot."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.dashboard.evidence import build_snapshot, validate_snapshot
from src.dashboard.models import EvidenceSnapshot

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, default=ROOT / "outputs/module15/evidence_snapshot.json"
    )
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    started = time.monotonic()
    result: dict[str, Any]
    if args.validate_only:
        snapshot = EvidenceSnapshot.model_validate_json(args.output.read_text(encoding="utf-8"))
        errors = validate_snapshot(ROOT, snapshot)
        result = {
            "status": "PASS" if not errors else "FAIL",
            "errors": errors,
            "snapshot_fingerprint": snapshot.snapshot_fingerprint,
            "runtime_seconds": round(time.monotonic() - started, 6),
        }
    else:
        if args.output.exists() and not args.force:
            existing = EvidenceSnapshot.model_validate_json(args.output.read_text(encoding="utf-8"))
            if not validate_snapshot(ROOT, existing):
                raise FileExistsError("valid_snapshot_exists_use_force")
        snapshot = build_snapshot(ROOT)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            snapshot.model_dump_json(indent=2, exclude_computed_fields=True) + "\n",
            encoding="utf-8",
        )
        manifest = {
            "schema_version": 1,
            "status": "CURRENT",
            "snapshot_fingerprint": snapshot.snapshot_fingerprint,
            "source_count": len(snapshot.sources),
            "value_count": len(snapshot.values),
            "mandatory_source_count": snapshot.mandatory_source_count,
            "optional_source_count": snapshot.optional_source_count,
            "source_checksums": snapshot.source_checksums,
        }
        manifest_path = args.output.with_name("evidence_manifest.json")
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        result = {
            **{k: v for k, v in manifest.items() if k not in {"source_checksums", "status"}},
            "status": "PASS",
            "runtime_seconds": round(time.monotonic() - started, 6),
        }
    print(json.dumps(result, indent=2 if args.json or args.verbose else None))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
