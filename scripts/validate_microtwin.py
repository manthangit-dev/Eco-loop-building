"""Validate cached Module 12 artifacts and persistence without retraining."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.microtwin.config import load_microtwin_settings

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    settings = load_microtwin_settings(ROOT / "config/microtwin.yaml")
    required = (
        "model_manifest.json",
        "thermal_model.json",
        "thermal_validation_report.json",
        "thermal_feature_schema.json",
        "split_manifest.json",
        "training_data_fingerprint.json",
        "demand_validation_report.json",
    )
    checksums = {
        name: hashlib.sha256((settings.model_directory / name).read_bytes()).hexdigest()
        for name in required
    }
    manifest = json.loads((settings.model_directory / required[0]).read_text())
    report = json.loads((settings.model_directory / required[2]).read_text())
    with sqlite3.connect(settings.database) as connection:
        schema = connection.execute("PRAGMA user_version").fetchone()[0]
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        foreign_keys = connection.execute("PRAGMA foreign_key_check").fetchall()
        counts = {
            table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("microtwin_models", "microtwin_rollouts", "microtwin_rankings")
        }
    checks = {
        "schema_8_additive": schema == 8,
        "integrity": integrity == "ok",
        "foreign_keys": not foreign_keys,
        "thermal_qualified": manifest["thermal_qualification"] is True,
        "beats_persistence": report["mae"] < report["persistence_mae"],
        "artifact_checksums": all(len(value) == 64 for value in checksums.values()),
        "records_present": all(value > 0 for value in counts.values()),
    }
    payload = {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "checksums": checksums,
        "record_counts": counts,
    }
    print(json.dumps(payload, indent=2))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
