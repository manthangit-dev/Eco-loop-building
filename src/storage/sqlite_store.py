"""Focused, thread-owned SQLite store for canonical states."""

from __future__ import annotations

import json
import math
import sqlite3
from pathlib import Path
from types import TracebackType
from typing import cast

from src.state.models import BuildingState, RunCompletion, RunMetadata
from src.storage.schema import SCHEMA_SQL, SCHEMA_VERSION


class StorageError(RuntimeError):
    pass


class DuplicateStateStorageError(StorageError):
    pass


class SQLiteStateStore:
    def __init__(
        self,
        database_path: Path,
        approved_root: Path,
        *,
        journal_mode: str = "WAL",
        busy_timeout_ms: int = 5000,
    ) -> None:
        path = database_path.resolve()
        path.relative_to(approved_root.resolve())
        if path == approved_root.resolve():
            raise ValueError("Database path must be below the approved root.")
        path.parent.mkdir(parents=True, exist_ok=True)
        self.database_path = path
        self.connection = sqlite3.connect(path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.connection.execute(f"PRAGMA busy_timeout = {int(busy_timeout_ms)}")
        mode = journal_mode.upper()
        if mode not in {"WAL", "DELETE"}:
            raise ValueError("Unsupported SQLite journal mode.")
        self.connection.execute(f"PRAGMA journal_mode = {mode}")
        self.closed = False
        self.commit_count = 0
        self.rollback_count = 0

    def initialise_schema(self) -> None:
        self.connection.executescript(SCHEMA_SQL)
        row = self.connection.execute(
            "SELECT value FROM schema_metadata WHERE key='schema_version'"
        ).fetchone()
        if row is not None and int(row["value"]) != SCHEMA_VERSION:
            raise StorageError("Unsupported existing schema version.")
        self.connection.execute(
            "INSERT OR IGNORE INTO schema_metadata(key,value) VALUES('schema_version',?)",
            (str(SCHEMA_VERSION),),
        )
        self.connection.commit()

    def schema_version(self) -> int:
        row = self.connection.execute(
            "SELECT value FROM schema_metadata WHERE key='schema_version'"
        ).fetchone()
        if row is None:
            raise StorageError("Schema is not initialized.")
        return int(row["value"])

    def begin_run(self, metadata: RunMetadata) -> None:
        self.connection.execute(
            """INSERT INTO simulation_runs(
                run_id,module,execution_mode,status,started_at_utc,energyplus_version,
                api_version,model_path,model_checksum,weather_path,weather_checksum,
                configuration_checksum,expected_snapshot_count,notes)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                metadata.run_id,
                metadata.module,
                metadata.execution_mode,
                metadata.status,
                metadata.started_at_utc,
                metadata.energyplus_version,
                metadata.api_version,
                metadata.model_path,
                metadata.model_checksum,
                metadata.weather_path,
                metadata.weather_checksum,
                metadata.configuration_checksum,
                metadata.expected_snapshot_count,
                metadata.notes,
            ),
        )
        self.connection.commit()

    @staticmethod
    def _finite(state: BuildingState) -> None:
        values = [
            state.outdoor.dry_bulb_c,
            state.outdoor.relative_humidity_percent,
            state.building_energy.facility_purchased_electricity_raw_j,
            state.building_energy.facility_demand_rate_w,
            state.building_energy.hvac_electricity_raw_j,
        ]
        values.extend(zone.mean_air_temperature_c for zone in state.zones)
        values.extend(zone.occupant_count for zone in state.zones)
        if not all(math.isfinite(value) for value in values):
            raise StorageError("Cannot store non-finite canonical values.")

    def append_state(self, state: BuildingState) -> None:
        self.append_states((state,))

    def append_states(self, states: tuple[BuildingState, ...]) -> None:
        try:
            self.connection.execute("BEGIN")
            for state in states:
                self._finite(state)
                clock = state.clock
                energy = state.building_energy
                cursor = self.connection.execute(
                    """INSERT INTO building_states VALUES(
                    NULL,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        state.run_id,
                        state.schema_version,
                        state.sequence,
                        state.source,
                        state.execution_mode,
                        state.captured_at_utc,
                        clock.environment_number,
                        clock.environment_type,
                        clock.calendar_year,
                        clock.month,
                        clock.day,
                        clock.day_of_year,
                        clock.day_of_week,
                        clock.hour,
                        clock.minute,
                        clock.current_time_hours,
                        clock.current_simulation_time_hours,
                        clock.zone_timestep_number,
                        clock.zone_timesteps_per_hour,
                        int(clock.warmup),
                        state.outdoor.dry_bulb_c,
                        state.outdoor.relative_humidity_percent,
                        energy.facility_purchased_electricity_raw_j,
                        energy.facility_demand_rate_w,
                        energy.hvac_electricity_raw_j,
                        energy.cooling_electricity_raw_j,
                        energy.heating_electricity_raw_j,
                        energy.meter_units,
                        state.raw_snapshot_sequence,
                        state.fingerprint,
                        state.to_json(),
                    ),
                )
                if cursor.lastrowid is None:
                    raise StorageError("SQLite did not return a building-state row ID.")
                state_id = cursor.lastrowid
                for zone in state.zones:
                    self.connection.execute(
                        """INSERT INTO zone_states VALUES(
                        NULL,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (
                            state_id,
                            zone.zone_id,
                            zone.exact_name,
                            zone.classification.value,
                            int(zone.occupancy_capable),
                            int(zone.is_plenum),
                            zone.mean_air_temperature_c,
                            zone.occupant_count,
                            zone.relative_humidity_percent,
                            zone.pmv,
                            zone.co2_ppm,
                            zone.effective_cooling_setpoint_c,
                            json.dumps([vars(item) for item in zone.availability]),
                            json.dumps([vars(item) for item in zone.quality_issues]),
                        ),
                    )
                for availability in state.sensor_availability:
                    self.connection.execute(
                        """INSERT INTO sensor_availability
                        VALUES(NULL,?,?,?,?,?)""",
                        (
                            state_id,
                            availability.field,
                            int(availability.available),
                            availability.source,
                            availability.reason,
                        ),
                    )
                for issue in state.quality_issues:
                    self.connection.execute(
                        """INSERT INTO state_quality_issues
                        VALUES(NULL,?,?,?,?,?)""",
                        (
                            state_id,
                            issue.code,
                            issue.severity,
                            issue.message,
                            issue.zone_id,
                        ),
                    )
            self.connection.commit()
            self.commit_count += 1
        except sqlite3.IntegrityError as exc:
            self.connection.rollback()
            self.rollback_count += 1
            raise DuplicateStateStorageError(str(exc)) from exc
        except BaseException:
            self.connection.rollback()
            self.rollback_count += 1
            raise

    def flush(self) -> None:
        self.connection.commit()
        self.commit_count += 1

    def latest_state(self, run_id: str) -> sqlite3.Row | None:
        return cast(
            sqlite3.Row | None,
            self.connection.execute(
                "SELECT * FROM building_states WHERE run_id=? ORDER BY sequence DESC LIMIT 1",
                (run_id,),
            ).fetchone(),
        )

    def states_after(self, run_id: str, sequence: int, limit: int) -> list[sqlite3.Row]:
        return self.connection.execute(
            """SELECT * FROM building_states WHERE run_id=? AND sequence>?
               ORDER BY sequence LIMIT ?""",
            (run_id, sequence, limit),
        ).fetchall()

    def recent_states(self, run_id: str, limit: int) -> list[sqlite3.Row]:
        return self.connection.execute(
            """SELECT * FROM building_states WHERE run_id=?
               ORDER BY sequence DESC LIMIT ?""",
            (run_id, limit),
        ).fetchall()

    def zone_history(
        self, run_id: str, zone_id: str, start_sequence: int, end_sequence: int
    ) -> list[sqlite3.Row]:
        return self.connection.execute(
            """SELECT b.sequence,z.* FROM zone_states z
               JOIN building_states b ON b.id=z.building_state_id
               WHERE b.run_id=? AND z.zone_id=? AND b.sequence BETWEEN ? AND ?
               ORDER BY b.sequence""",
            (run_id, zone_id, start_sequence, end_sequence),
        ).fetchall()

    def list_runs(self) -> list[sqlite3.Row]:
        return self.connection.execute(
            "SELECT * FROM simulation_runs ORDER BY started_at_utc"
        ).fetchall()

    def get_run(self, run_id: str) -> sqlite3.Row | None:
        return cast(
            sqlite3.Row | None,
            self.connection.execute(
                "SELECT * FROM simulation_runs WHERE run_id=?", (run_id,)
            ).fetchone(),
        )

    def finalise_run(self, completion: RunCompletion) -> None:
        cursor = self.connection.execute(
            """UPDATE simulation_runs SET status=?,finished_at_utc=?,
            persisted_snapshot_count=?,first_sequence=?,last_sequence=?,
            first_simulation_timestamp=?,last_simulation_timestamp=?,
            severe_count=?,fatal_count=?,callback_error_count=?,api_error_count=?,
            subscriber_error_count=?,persistence_error_count=?,queue_drained=?,
            actuator_access_count=?,control_decision_count=? WHERE run_id=?""",
            (
                completion.status,
                completion.finished_at_utc,
                completion.persisted_snapshot_count,
                completion.first_sequence,
                completion.last_sequence,
                completion.first_simulation_timestamp,
                completion.last_simulation_timestamp,
                completion.severe_count,
                completion.fatal_count,
                completion.callback_error_count,
                completion.api_error_count,
                completion.subscriber_error_count,
                completion.persistence_error_count,
                int(completion.queue_drained),
                completion.actuator_access_count,
                completion.control_decision_count,
                completion.run_id,
            ),
        )
        if cursor.rowcount != 1:
            raise StorageError("Run finalization did not update exactly one row.")
        self.connection.commit()

    def integrity_check(self) -> str:
        return str(self.connection.execute("PRAGMA integrity_check").fetchone()[0])

    def foreign_key_check(self) -> list[sqlite3.Row]:
        return self.connection.execute("PRAGMA foreign_key_check").fetchall()

    def close(self) -> None:
        if not self.closed:
            self.connection.close()
            self.closed = True

    def __enter__(self) -> SQLiteStateStore:
        return self

    def __exit__(
        self,
        _exc_type: type[BaseException] | None,
        _exc: BaseException | None,
        _traceback: TracebackType | None,
    ) -> None:
        self.close()
