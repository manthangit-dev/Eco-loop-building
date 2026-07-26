"""Transactional safety audit repository."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict
from pathlib import Path

from src.safety.models import GuardDecision, GuardedCommand
from src.safety.write_gate import WriteAttempt
from src.storage.safety_schema import migrate_safety_schema


class SafetyStore:
    def __init__(self, path: Path, approved_root: Path, *, commit_interval: int = 1) -> None:
        resolved = path.resolve()
        resolved.relative_to(approved_root.resolve())
        resolved.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(resolved, check_same_thread=False)
        self.connection.execute("PRAGMA foreign_keys=ON")
        migrate_safety_schema(self.connection)
        row = self.connection.execute(
            "SELECT COALESCE(MAX(persisted_order),0) FROM safety_guard_decisions"
        ).fetchone()
        self._order = int(row[0])
        self._commit_interval = commit_interval
        self._pending = 0

    def append(
        self,
        decision: GuardDecision,
        command: GuardedCommand | None,
        actuator_identity: str = "Zone Temperature Control|Cooling Setpoint|SPACE3-1|C",
    ) -> None:
        if self._pending == 0:
            self.connection.execute("BEGIN")
        try:
            self._order += 1
            self.connection.execute(
                """INSERT INTO safety_guard_decisions VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    decision.guard_decision_id,
                    decision.command_id,
                    decision.run_id,
                    decision.environment_id,
                    decision.source_state_sequence,
                    actuator_identity,
                    json.dumps(decision.requested_value, allow_nan=False),
                    decision.applied_value,
                    decision.outcome.value,
                    decision.reason.value,
                    decision.previous_safe_value,
                    decision.safety_schema_version,
                    decision.current_sequence,
                    decision.fingerprint,
                    self._order,
                ),
            )
            for index, reason in enumerate(decision.violations):
                self.connection.execute(
                    "INSERT INTO safety_guard_violations VALUES(?,?,?,?,?,?,?)",
                    (
                        f"{decision.guard_decision_id}:{index}",
                        decision.guard_decision_id,
                        "guard_validation",
                        reason.value,
                        None,
                        None,
                        "{}",
                    ),
                )
            if command is not None:
                self.connection.execute(
                    "INSERT INTO guarded_commands VALUES(?,?,?,?,?,?,?)",
                    (
                        command.command_id,
                        command.guard_decision_id,
                        command.run_id,
                        command.environment_id,
                        json.dumps(asdict(command), default=str, sort_keys=True),
                        command.expires_after_sequence,
                        "PENDING",
                    ),
                )
            self._pending += 1
            if self._pending >= self._commit_interval:
                self.connection.commit()
                self._pending = 0
        except Exception:
            self.connection.rollback()
            self._pending = 0
            raise

    def append_attempt(self, attempt: WriteAttempt, context: dict[str, object]) -> None:
        self.connection.execute(
            """INSERT INTO physical_write_attempts(guarded_command_id,guard_decision_id,
            operation,permitted,applied_value,callback_context_json,reason_code)
            VALUES(?,?,?,?,?,?,?)""",
            (
                attempt.command_id,
                attempt.guard_decision_id,
                attempt.operation,
                int(attempt.permitted),
                attempt.value,
                json.dumps(context, sort_keys=True),
                str(attempt.reason),
            ),
        )
        self.connection.commit()
        if attempt.command_id is not None and attempt.permitted:
            self.connection.execute(
                "UPDATE guarded_commands SET physical_submission_status='SUBMITTED' "
                "WHERE command_id=?",
                (attempt.command_id,),
            )
            self.connection.commit()

    def close(self) -> None:
        if self._pending:
            self.connection.commit()
            self._pending = 0
        self.connection.close()

    def __enter__(self) -> SafetyStore:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()
