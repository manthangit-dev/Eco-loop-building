"""Transactional idempotent persistence for planning evidence."""

import sqlite3
from pathlib import Path

from src.planning.models import CandidatePlan, PlanningContext
from src.planning.provenance import planning_fingerprint
from src.storage.planning_schema import migrate


class PlanningStore:
    def __init__(self, database: Path, output_root: Path) -> None:
        database.resolve().relative_to(output_root.resolve())
        database.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(database)
        migrate(self.connection)

    def persist(self, context: PlanningContext, plans: tuple[CandidatePlan, ...]) -> None:
        c = self.connection
        c.execute("BEGIN")
        try:
            c.execute(
                "INSERT OR IGNORE INTO planning_contexts VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    context.context_id,
                    context.run_id,
                    context.environment_id,
                    context.source_state_id,
                    context.planning_timestamp,
                    context.target_zone,
                    context.actuator_identity,
                    context.horizon,
                    context.context_fingerprint,
                    context.prohibited_future_source_count,
                    context.uncertainty,
                    context.schema_version,
                    context.model_dump_json(),
                ),
            )
            for point in context.forecasts:
                c.execute(
                    "INSERT OR IGNORE INTO planning_forecast_points VALUES(?,?,?,?,?,?,?,?,?,?)",
                    (
                        context.context_id,
                        point.forecast_type,
                        point.sequence,
                        point.simulation_timestamp,
                        point.zone,
                        point.value,
                        point.units,
                        point.uncertainty,
                        point.source,
                        planning_fingerprint(point.provenance),
                    ),
                )
            for plan in plans:
                c.execute(
                    "INSERT OR IGNORE INTO candidate_plans VALUES(?,?,?,?,?,?,?,?,?,?)",
                    (
                        plan.plan_id,
                        context.context_id,
                        plan.strategy_type,
                        plan.validation_status,
                        plan.advisory_score,
                        plan.first_action_guard_outcome,
                        plan.first_action_guard_reason,
                        plan.plan_fingerprint,
                        plan.schema_version,
                        plan.model_dump_json(),
                    ),
                )
                for action in plan.actions:
                    c.execute(
                        "INSERT OR IGNORE INTO candidate_actions VALUES(?,?,?,?,?,?,?,?,?,?)",
                        (
                            plan.plan_id,
                            action.action_sequence,
                            action.timestep_offset,
                            action.intended_simulation_timestamp,
                            action.actuator_identity,
                            action.requested_value,
                            action.units,
                            action.action_type,
                            action.rationale_code,
                            int(action.requires_execution_time_guard_validation),
                        ),
                    )
                for name, value in plan.score_components.items():
                    c.execute(
                        "INSERT OR IGNORE INTO plan_score_components VALUES(?,?,?,?,?,?)",
                        (plan.plan_id, name, value, 1.0, value, name),
                    )
                for sequence, reason in enumerate(plan.rejection_reasons):
                    c.execute(
                        "INSERT OR IGNORE INTO plan_validation_events VALUES(?,?,?,?,?)",
                        (plan.plan_id, sequence, "ERROR", reason, "{}"),
                    )
            c.commit()
        except Exception:
            c.rollback()
            raise

    def close(self) -> None:
        self.connection.close()

    def __enter__(self) -> "PlanningStore":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
