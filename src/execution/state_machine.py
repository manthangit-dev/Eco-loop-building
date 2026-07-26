"""Explicit deterministic execution state machine."""

from src.execution.errors import InvalidTransitionError
from src.execution.models import ExecutionState, StateTransition

ALLOWED: dict[ExecutionState, frozenset[ExecutionState]] = {
    ExecutionState.IDLE: frozenset({ExecutionState.PREFLIGHT}),
    ExecutionState.PREFLIGHT: frozenset({ExecutionState.APPROVAL_REQUIRED, ExecutionState.ABORTED}),
    ExecutionState.APPROVAL_REQUIRED: frozenset({ExecutionState.ARMED, ExecutionState.ABORTED}),
    ExecutionState.ARMED: frozenset({ExecutionState.WAITING_FOR_LIVE_STATE}),
    ExecutionState.WAITING_FOR_LIVE_STATE: frozenset(
        {ExecutionState.EXECUTING, ExecutionState.FALLBACK_ACTIVE, ExecutionState.ABORTED}
    ),
    ExecutionState.EXECUTING: frozenset(
        {ExecutionState.HOLDING, ExecutionState.FALLBACK_ACTIVE, ExecutionState.RESETTING_TO_NATIVE}
    ),
    ExecutionState.HOLDING: frozenset(
        {
            ExecutionState.EXECUTING,
            ExecutionState.FALLBACK_ACTIVE,
            ExecutionState.RESETTING_TO_NATIVE,
        }
    ),
    ExecutionState.FALLBACK_ACTIVE: frozenset({ExecutionState.RESETTING_TO_NATIVE}),
    ExecutionState.RESETTING_TO_NATIVE: frozenset(
        {ExecutionState.COMPLETED, ExecutionState.ABORTED, ExecutionState.FAILED}
    ),
    ExecutionState.COMPLETED: frozenset(),
    ExecutionState.ABORTED: frozenset(),
    ExecutionState.FAILED: frozenset(),
}


class ExecutionStateMachine:
    def __init__(self) -> None:
        self.state = ExecutionState.IDLE
        self.transitions: list[StateTransition] = []

    def transition(self, target: ExecutionState, reason: str) -> StateTransition:
        if target not in ALLOWED[self.state]:
            raise InvalidTransitionError("invalid_state_transition")
        record = StateTransition(
            sequence=len(self.transitions) + 1,
            from_state=self.state,
            to_state=target,
            reason_code=reason,
        )
        self.transitions.append(record)
        self.state = target
        return record
