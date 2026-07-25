"""Inspect Module 6 SQLite data through predefined read-only queries."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.state.config import load_state_settings  # noqa: E402
from src.storage.queries import open_read_only, rows_as_dicts, table_counts  # noqa: E402

STATE_COLUMNS = """
id, run_id, schema_version, sequence, source, execution_mode, captured_at_utc,
month, day, hour, minute, current_simulation_time_hours, outdoor_dry_bulb_c,
outdoor_relative_humidity_percent, facility_demand_rate_w, fingerprint
"""


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-config", type=Path, default=Path("config/state_bus.yaml"))
    parser.add_argument("--mode", choices=("replay", "live"), required=True)
    parser.add_argument("--run-id")
    parser.add_argument("--zone-id")
    parser.add_argument("--recent", type=int, default=5)
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    config = args.state_config if args.state_config.is_absolute() else root / args.state_config
    settings = load_state_settings(config, root)
    with open_read_only(settings.database_path(args.mode)) as connection:
        runs = connection.execute(
            "SELECT * FROM simulation_runs ORDER BY started_at_utc"
        ).fetchall()
        run_id = args.run_id or (str(runs[-1]["run_id"]) if runs else "")
        latest = connection.execute(
            f"""SELECT {STATE_COLUMNS} FROM building_states
                WHERE run_id=? ORDER BY sequence DESC LIMIT 1""",
            (run_id,),
        ).fetchall()
        recent = connection.execute(
            f"""SELECT {STATE_COLUMNS} FROM building_states
                WHERE run_id=? ORDER BY sequence DESC LIMIT ?""",
            (run_id, args.recent),
        ).fetchall()
        zones = connection.execute(
            "SELECT DISTINCT zone_id,exact_name,classification FROM zone_states ORDER BY zone_id"
        ).fetchall()
        zone_history = []
        if args.zone_id:
            zone_history = connection.execute(
                """SELECT b.sequence,z.* FROM zone_states z JOIN building_states b
                   ON b.id=z.building_state_id WHERE b.run_id=? AND z.zone_id=?
                   ORDER BY b.sequence DESC LIMIT ?""",
                (run_id, args.zone_id, args.recent),
            ).fetchall()
        payload = {
            "database": str(settings.database_path(args.mode)),
            "counts": table_counts(connection),
            "runs": rows_as_dicts(runs),
            "latest": rows_as_dicts(latest),
            "recent": rows_as_dicts(recent),
            "zone_classifications": rows_as_dicts(zones),
            "zone_history": rows_as_dicts(zone_history),
            "integrity_check": connection.execute("PRAGMA integrity_check").fetchone()[0],
            "foreign_key_violations": rows_as_dicts(
                connection.execute("PRAGMA foreign_key_check").fetchall()
            ),
        }
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
