"""Independent deterministic guard memory."""

from __future__ import annotations

from dataclasses import dataclass, field

from src.safety.models import GuardDecision, GuardedCommand, ProposedCommand


@dataclass
class SafetyMemory:
    run_id: str
    environment_id: str
    last_safe: GuardedCommand | None = None
    last_submitted_value: float | None = None
    last_native_reset_sequence: int = 0
    last_proposal: ProposedCommand | None = None
    last_decision: GuardDecision | None = None
    last_valid_state_sequence: int = 0
    observed: dict[str, tuple[str, GuardDecision, GuardedCommand | None]] = field(
        default_factory=dict
    )
    shutdown: bool = False
    disabled: bool = False

    def reset_for_run(self, run_id: str, environment_id: str) -> None:
        self.run_id, self.environment_id = run_id, environment_id
        self.last_safe = None
        self.last_submitted_value = None
        self.last_native_reset_sequence = 0
        self.last_proposal = None
        self.last_decision = None
        self.last_valid_state_sequence = 0
        self.observed.clear()
        self.shutdown = self.disabled = False

    def reset_for_environment(self, environment_id: str) -> None:
        self.reset_for_run(self.run_id, environment_id)

    def warmup_complete(self) -> None:
        self.last_valid_state_sequence = 0

    def disable(self) -> None:
        self.disabled = True
        self.last_safe = None

    def begin_shutdown(self) -> None:
        self.shutdown = True
        self.last_safe = None
