"""Validate a completed Module 6 replay or live SQLite database."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.state.config import load_state_settings  # noqa: E402
from src.storage.queries import open_read_only, table_counts  # noqa: E402
from src.storage.schema import SCHEMA_VERSION  # noqa: E402


@dataclass(frozen=True)
class Check:
    name: str
    passed: bool
    detail: str


def validate(config: Path, mode: str) -> tuple[list[Check], Path]:
    root = config.resolve().parents[1]
    settings = load_state_settings(config, root)
    output = settings.replay_output if mode == "replay" else settings.live_output
    database = settings.database_path(mode)
    checks = [
        Check(
            "Database exists",
            database.is_file() and database.stat().st_size > 0,
            str(database),
        )
    ]
    if not checks[0].passed:
        return checks, output / "state_storage_validation_summary.json"
    with open_read_only(database) as connection:
        counts = table_counts(connection)
        version_row = connection.execute(
            "SELECT value FROM schema_metadata WHERE key='schema_version'"
        ).fetchone()
        runs = connection.execute("SELECT * FROM simulation_runs").fetchall()
        run = runs[0] if len(runs) == 1 else None
        integrity = str(connection.execute("PRAGMA integrity_check").fetchone()[0])
        foreign = connection.execute("PRAGMA foreign_key_check").fetchall()
        sequence = connection.execute(
            """SELECT COUNT(*),COUNT(DISTINCT sequence),MIN(sequence),MAX(sequence),
               MIN(current_simulation_time_hours),MAX(current_simulation_time_hours)
               FROM building_states"""
        ).fetchone()
        zones = connection.execute(
            """
            SELECT exact_name, classification, COUNT(*) n
            FROM zone_states
            GROUP BY exact_name, classification
            """
        ).fetchall()
        invalid_values = int(
            connection.execute(
                """SELECT COUNT(*) FROM zone_states WHERE occupant_count<0 OR
                   relative_humidity_percent<0 OR relative_humidity_percent>100"""
            ).fetchone()[0]
        )
        missing_optional = int(
            connection.execute(
                "SELECT COUNT(*) FROM zone_states WHERE pmv IS NULL AND co2_ppm IS NULL"
            ).fetchone()[0]
        )
        fingerprints = int(
            connection.execute(
                "SELECT COUNT(*) FROM building_states WHERE length(fingerprint)=64"
            ).fetchone()[0]
        )
        fingerprint_mismatches = int(
            connection.execute(
                """
                SELECT COUNT(*) FROM building_states
                WHERE json_extract(canonical_json, '$.fingerprint') <> fingerprint
                """
            ).fetchone()[0]
        )
        non_monotonic_times = int(
            connection.execute(
                """
                SELECT COUNT(*) FROM (
                    SELECT current_simulation_time_hours,
                           LAG(current_simulation_time_hours) OVER (ORDER BY sequence) previous
                    FROM building_states
                ) WHERE previous IS NOT NULL AND current_simulation_time_hours <= previous
                """
            ).fetchone()[0]
        )
    expected = settings.expected_snapshot_count
    zone_map = {str(row["exact_name"]): str(row["classification"]) for row in zones}
    manifest = json.loads((root / "models/MODEL_MANIFEST.json").read_text())
    source_hash = hashlib.sha256(
        (root / "models/source/5ZoneAirCooled_v26_1_original.idf").read_bytes()
    ).hexdigest()
    baseline_hash = hashlib.sha256(
        (root / "models/baseline/thermoledger_5zone_baseline.idf").read_bytes()
    ).hexdigest()
    weather_hash = hashlib.sha256(
        (root / "weather/input" / manifest["weather_filename"]).read_bytes()
    ).hexdigest()
    checks.extend(
        [
            Check(
                "Schema version",
                version_row is not None and int(version_row[0]) == SCHEMA_VERSION,
                str(version_row[0] if version_row else None),
            ),
            Check(
                "Single completed run",
                run is not None and run["status"] == "COMPLETED",
                str(len(runs)),
            ),
            Check(
                "State count", counts["building_states"] == expected, str(counts["building_states"])
            ),
            Check(
                "Persisted count metadata",
                run is not None and run["persisted_snapshot_count"] == expected,
                str(run["persisted_snapshot_count"] if run else None),
            ),
            Check(
                "Sequence uniqueness",
                sequence[0] == sequence[1] == expected
                and sequence[2] == 1
                and sequence[3] == expected,
                str(tuple(sequence)),
            ),
            Check("Monotonic simulation time", non_monotonic_times == 0, str(non_monotonic_times)),
            Check(
                "Zone row count",
                counts["zone_states"] == expected * settings.expected_zone_count,
                str(counts["zone_states"]),
            ),
            Check("All zones", set(zone_map) == set(manifest["zone_names"]), str(zone_map)),
            Check(
                "Plenum classification",
                zone_map.get("PLENUM-1") == "PLENUM",
                str(zone_map.get("PLENUM-1")),
            ),
            Check(
                "Occupied zones not plenum",
                all(zone_map.get(f"SPACE{i}-1") == "OCCUPIED_CONDITIONED" for i in range(1, 6)),
                "SPACE1-1..SPACE5-1",
            ),
            Check("Canonical value constraints", invalid_values == 0, str(invalid_values)),
            Check(
                "Optional null preservation",
                missing_optional == counts["zone_states"],
                str(missing_optional),
            ),
            Check(
                "Sensor availability",
                counts["sensor_availability"] > 0,
                str(counts["sensor_availability"]),
            ),
            Check("Fingerprints", fingerprints == expected, str(fingerprints)),
            Check(
                "Canonical fingerprint parity",
                fingerprint_mismatches == 0,
                str(fingerprint_mismatches),
            ),
            Check(
                "Subscriber/persistence errors",
                run is not None
                and run["subscriber_error_count"] == 0
                and run["persistence_error_count"] == 0,
                "must be zero",
            ),
            Check(
                "Queue drained",
                run is not None and run["queue_drained"] == 1,
                str(run["queue_drained"] if run else None),
            ),
            Check("SQLite integrity", integrity == "ok", integrity),
            Check("Foreign keys", not foreign, str(len(foreign))),
            Check(
                "Source checksum",
                source_hash == manifest["repository_source_copy_sha256"],
                source_hash,
            ),
            Check(
                "Baseline checksum",
                baseline_hash == manifest["derived_baseline_sha256"],
                baseline_hash,
            ),
            Check("Weather checksum", weather_hash == manifest["weather_sha256"], weather_hash),
            Check(
                "No actuator/control",
                run is not None
                and run["actuator_access_count"] == 0
                and run["control_decision_count"] == 0,
                "must be zero",
            ),
        ]
    )
    summary = {
        "mode": mode,
        "status": "PASS" if all(item.passed for item in checks) else "FAIL",
        "database_path": str(database),
        "database_size_bytes": database.stat().st_size,
        "counts": counts,
        "checks": [asdict(item) for item in checks],
    }
    path = output / "state_storage_validation_summary.json"
    path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return checks, path


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-config", type=Path, default=Path("config/state_bus.yaml"))
    parser.add_argument("--mode", choices=("replay", "live"), required=True)
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    config = args.state_config if args.state_config.is_absolute() else root / args.state_config
    checks, path = validate(config, args.mode)
    for item in checks:
        print(f"[{'PASS' if item.passed else 'FAIL'}] {item.name}: {item.detail}")
    print(f"Validation summary: {path}")
    return 0 if all(item.passed for item in checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
