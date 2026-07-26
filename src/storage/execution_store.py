"""Transactional persistence for approval and execution evidence."""

from __future__ import annotations

import json
import math
import sqlite3

from src.execution.models import ExecutionApproval, ExecutionReport
from src.planning.provenance import planning_fingerprint
from src.storage.execution_schema import migrate


class ExecutionStore:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection
        migrate(connection)

    def persist_approval(self, approval: ExecutionApproval) -> None:
        payload = approval.model_dump_json()
        existing = self.connection.execute(
            "SELECT approval_json FROM execution_approvals WHERE approval_id=?",
            (approval.approval_id,),
        ).fetchone()
        if existing and existing[0] != payload:
            raise ValueError("conflicting_approval")
        self.connection.execute(
            "INSERT OR IGNORE INTO execution_approvals VALUES(?,?,?,?,?,?,?,?)",
            (
                approval.approval_id,
                payload,
                approval.execution_mode.value,
                approval.selected_plan_id,
                approval.expires_at.isoformat(),
                "ACTIVE",
                approval.consumed_session_id,
                approval.approval_fingerprint,
            ),
        )
        self.connection.commit()

    def persist_report(self, report: ExecutionReport) -> None:
        payload = report.model_dump(mode="json")
        values = [item.action.requested_value for item in report.actions]
        if any(not math.isfinite(value) for value in values):
            raise ValueError("non_finite_execution_value")
        fingerprint = planning_fingerprint(payload)
        with self.connection:
            self.connection.execute(
                "INSERT OR IGNORE INTO execution_sessions VALUES(?,?,?,?,?,?,?,?,?)",
                (
                    report.session_id,
                    report.approval_id,
                    report.mode.value,
                    report.final_state.value,
                    report.physical_set_calls,
                    report.physical_reset_calls,
                    report.fallback_activation_count,
                    json.dumps(payload, sort_keys=True),
                    fingerprint,
                ),
            )
            for transition in report.transitions:
                self.connection.execute(
                    "INSERT OR IGNORE INTO execution_state_transitions VALUES(?,?,?,?,?)",
                    (
                        report.session_id,
                        transition.sequence,
                        transition.from_state.value,
                        transition.to_state.value,
                        transition.reason_code,
                    ),
                )
            for outcome in report.actions:
                self.connection.execute(
                    "INSERT OR IGNORE INTO execution_actions VALUES(?,?,?,?,?,?,?)",
                    (
                        report.session_id,
                        outcome.action.plan_action_id,
                        outcome.action.action_sequence,
                        outcome.action.requested_value,
                        outcome.guard_outcome,
                        outcome.writer_status,
                        outcome.terminal_status,
                    ),
                )
            self.connection.execute(
                "INSERT OR IGNORE INTO execution_resets VALUES(?,?,?,?)",
                (
                    report.session_id,
                    1,
                    "mandatory_native_reset",
                    "SUCCESS" if report.mandatory_native_reset else "FAILED",
                ),
            )
            self.connection.execute(
                "UPDATE execution_approvals SET status='CONSUMED', consumed_session_id=? "
                "WHERE approval_id=?",
                (report.session_id, report.approval_id),
            )
