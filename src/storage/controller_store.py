"""SQLite persistence for Module 7 controller records."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict
from pathlib import Path

from src.control.models import (
    SAFETY_GUARD_PENDING,
    CommandOutcome,
    ControlCommand,
    ControlDecision,
    ControllerRunCompletion,
    ControllerRunMetadata,
)
from src.storage.controller_schema import migrate_controller_schema


class ControllerStore:
    def __init__(
        self, path: Path, approved_root: Path, *, allow_safety_schema: bool = False
    ) -> None:
        resolved = path.resolve()
        resolved.relative_to(approved_root.resolve())
        resolved.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(resolved)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys=ON")
        self.connection.execute("PRAGMA journal_mode=WAL")
        migrate_controller_schema(self.connection, allow_safety_schema=allow_safety_schema)

    def begin_run(self, item: ControllerRunMetadata) -> None:
        self.connection.execute(
            """INSERT INTO controller_runs(run_id,simulation_run_id,mode,status,
            started_at_utc,model_checksum,weather_checksum,expected_state_count,
            safety_guard_status) VALUES(?,?,?,'RUNNING',?,?,?,?,?)""",
            (
                item.run_id,
                item.simulation_run_id,
                item.mode,
                item.started_at_utc,
                item.model_checksum,
                item.weather_checksum,
                item.expected_state_count,
                SAFETY_GUARD_PENDING,
            ),
        )
        self.connection.commit()

    def append(self, decision: ControlDecision, command: ControlCommand | None) -> None:
        self.connection.execute("BEGIN")
        try:
            self._insert(decision, command)
            self.connection.commit()
        except BaseException:
            self.connection.rollback()
            raise

    def append_batch(self, items: list[tuple[ControlDecision, ControlCommand | None]]) -> None:
        self.connection.execute("BEGIN")
        try:
            for decision, command in items:
                self._insert(decision, command)
            self.connection.commit()
        except BaseException:
            self.connection.rollback()
            raise

    def _insert(self, decision: ControlDecision, command: ControlCommand | None) -> None:
        self.connection.execute(
            """INSERT INTO control_decisions VALUES(
                ?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                decision.decision_id,
                decision.run_id,
                decision.decision_sequence,
                decision.based_on_state_sequence,
                decision.based_on_state_fingerprint,
                decision.created_at_utc,
                decision.target_zone_id,
                decision.target_zone_name,
                decision.controller_mode_before.value,
                decision.controller_mode_after.value,
                decision.reason_code.value,
                decision.explanation,
                decision.occupancy,
                decision.zone_temperature_celsius,
                decision.baseline_setpoint_celsius,
                decision.requested_setpoint_celsius,
                decision.approved_setpoint_celsius,
                int(decision.clamped),
                decision.action_type.value,
                decision.command_ttl,
                decision.intended_effective_sequence,
                decision.actuator.key,
                int(decision.shadow_mode),
                decision.safety_guard_status,
                json.dumps(decision.validation_issues),
            ),
        )
        if command is not None:
            self.connection.execute(
                """INSERT INTO control_commands VALUES(
                    ?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    command.command_id,
                    command.decision_id,
                    decision.run_id,
                    command.target_zone_id,
                    command.target_zone_name,
                    command.actuator.key,
                    command.setpoint_celsius,
                    command.issued_from_sequence,
                    command.valid_from_sequence,
                    command.expires_after_sequence,
                    int(command.reset_required),
                    command.mode.value,
                    command.reason.value,
                    int(command.shadow_mode),
                    command.fingerprint,
                ),
            )

    def append_event(
        self,
        run_id: str,
        command_id: str | None,
        event_type: str,
        sequence: int,
        timestamp: str,
        value: float | None,
        detail: str,
    ) -> None:
        self.connection.execute(
            """INSERT INTO controller_events(
            run_id,command_id,event_type,state_sequence,simulation_timestamp,
            value_celsius,detail) VALUES(?,?,?,?,?,?,?)""",
            (run_id, command_id, event_type, sequence, timestamp, value, detail),
        )
        self.connection.commit()

    def append_outcome(self, item: CommandOutcome) -> None:
        self.connection.execute(
            "INSERT OR IGNORE INTO command_outcomes VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            tuple(asdict(item).values()),
        )
        self.connection.commit()

    def populate_observed_outcomes(self, run_id: str) -> int:
        """Link every real command to its subsequent stored canonical state."""
        before = int(self.connection.execute("SELECT COUNT(*) FROM command_outcomes").fetchone()[0])
        self.connection.execute(
            """INSERT OR IGNORE INTO command_outcomes(
            outcome_id,command_id,observed_state_sequence,event_type,
            effective_setpoint_celsius,zone_temperature_celsius,occupancy,
            outdoor_temperature_celsius,facility_electricity_raw_j,
            hvac_electricity_raw_j,association_label)
            SELECT c.command_id || ':' || b.sequence,c.command_id,b.sequence,'OBSERVED',
                   z.effective_cooling_setpoint_c,z.mean_air_temperature_c,z.occupant_count,
                   b.outdoor_dry_bulb_c,b.facility_purchased_electricity_raw_j,
                   b.hvac_electricity_raw_j,'post-command association'
            FROM control_commands c
            JOIN building_states b ON b.run_id=? AND b.sequence=c.valid_from_sequence
            JOIN zone_states z ON z.building_state_id=b.id AND z.zone_id=c.target_zone_id
            WHERE c.run_id=? AND c.shadow_mode=0""",
            (run_id, run_id),
        )
        self.connection.commit()
        after = int(self.connection.execute("SELECT COUNT(*) FROM command_outcomes").fetchone()[0])
        return after - before

    def finalise(self, item: ControllerRunCompletion) -> None:
        self.connection.execute(
            """UPDATE controller_runs SET status=?,finished_at_utc=?,state_count=?,
            decision_count=?,command_count=?,set_call_count=?,reset_count=?,expiry_count=?,
            rejected_count=?,api_error_count=?,callback_error_count=?,
            actuator_access_count=? WHERE run_id=?""",
            (
                item.status,
                item.finished_at_utc,
                item.state_count,
                item.decision_count,
                item.command_count,
                item.set_call_count,
                item.reset_count,
                item.expiry_count,
                item.rejected_count,
                item.api_error_count,
                item.callback_error_count,
                int(item.set_call_count > 0),
                item.run_id,
            ),
        )
        self.connection.commit()

    def counts(self) -> dict[str, int]:
        return {
            table: int(self.connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
            for table in (
                "controller_runs",
                "control_decisions",
                "control_commands",
                "controller_events",
                "command_outcomes",
            )
        }

    def close(self) -> None:
        self.connection.close()

    def __enter__(self) -> ControllerStore:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()
