"""Deterministic, exactly-once plan action scheduler."""

from __future__ import annotations

from src.execution.errors import ExecutionValidationError
from src.execution.models import ScheduledAction
from src.planning.models import CandidatePlan
from src.planning.provenance import planning_fingerprint


class ActionScheduler:
    def __init__(self, plan: CandidatePlan, maximum_actions: int, hold: int) -> None:
        if len(plan.actions) > maximum_actions:
            raise ExecutionValidationError("action_count_limit")
        self.actions = tuple(
            ScheduledAction(
                plan_action_id=planning_fingerprint(
                    {"plan_id": plan.plan_id, "action": action.model_dump(mode="json")}
                ),
                action_sequence=action.action_sequence,
                timestep_offset=action.timestep_offset,
                intended_simulation_timestamp=action.intended_simulation_timestamp,
                earliest_timestep=action.timestep_offset,
                latest_timestep=action.timestep_offset + hold,
                requested_value=action.requested_value,
                units=action.units,
                action_type=action.action_type,
            )
            for action in sorted(plan.actions, key=lambda item: item.action_sequence)
        )
        if tuple(item.action_sequence for item in self.actions) != tuple(range(len(self.actions))):
            raise ExecutionValidationError("changed_action_sequence")
        self.completed: set[str] = set()

    def due(self, timestep: int) -> ScheduledAction | None:
        for action in self.actions:
            if action.plan_action_id in self.completed:
                continue
            if timestep < action.earliest_timestep:
                return None
            if timestep > action.latest_timestep:
                raise ExecutionValidationError("late_action")
            return action
        return None

    def complete(self, action: ScheduledAction) -> None:
        if action.plan_action_id in self.completed:
            raise ExecutionValidationError("duplicate_action")
        if action not in self.actions:
            raise ExecutionValidationError("unexpected_action")
        self.completed.add(action.plan_action_id)
