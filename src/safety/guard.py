"""Deterministic independent safety decision engine."""

from __future__ import annotations

from collections.abc import Callable

from src.safety.config import SafetySettings
from src.safety.memory import SafetyMemory
from src.safety.models import (
    GuardDecision,
    GuardedCommand,
    GuardOutcome,
    ProposedCommand,
    SafetyReason,
    canonical_hash,
    make_guarded_command,
    numeric_reason,
)

Persist = Callable[[GuardDecision, GuardedCommand | None], None]


class SafetyGuard:
    def __init__(
        self, settings: SafetySettings, memory: SafetyMemory, persist: Persist | None = None
    ) -> None:
        self.settings, self.memory, self.persist = settings, memory, persist
        self.persistence_failures = 0
        self.internal_errors = 0
        self.last_persistence_error: str | None = None

    def evaluate(self, proposal: ProposedCommand) -> tuple[GuardDecision, GuardedCommand | None]:
        try:
            return self._evaluate(proposal)
        except Exception:
            self.internal_errors += 1
            decision = GuardDecision(
                canonical_hash({"internal_error": str(proposal.command_id)}),
                proposal.command_id,
                proposal.run_id,
                proposal.environment_id,
                GuardOutcome.REJECT_NO_WRITE,
                SafetyReason.GUARD_INTERNAL_ERROR,
                None,
                None,
                None,
                proposal.source_state_sequence,
                proposal.current_sequence,
                self.settings.schema_version,
                (SafetyReason.GUARD_INTERNAL_ERROR,),
            )
            return decision, None

    def _evaluate(self, proposal: ProposedCommand) -> tuple[GuardDecision, GuardedCommand | None]:
        if not self.settings.enabled or self.memory.disabled:
            return self._finish(
                proposal, GuardOutcome.RESET_TO_NATIVE, SafetyReason.DISABLED_CONTROL, None
            )
        if self.memory.shutdown:
            return self._finish(
                proposal, GuardOutcome.RESET_TO_NATIVE, SafetyReason.SHUTDOWN_IN_PROGRESS, None
            )
        if not proposal.api_ready:
            return self._finish(
                proposal, GuardOutcome.REJECT_NO_WRITE, SafetyReason.SIMULATION_NOT_READY, None
            )
        if proposal.warmup:
            return self._finish(
                proposal, GuardOutcome.REJECT_NO_WRITE, SafetyReason.WARMUP_STATE_REJECTED, None
            )
        if proposal.schema_version != self.settings.schema_version:
            return self._finish(
                proposal,
                GuardOutcome.REJECT_NO_WRITE,
                SafetyReason.UNSUPPORTED_SCHEMA_VERSION,
                None,
            )
        if not proposal.command_id:
            return self._finish(
                proposal, GuardOutcome.REJECT_NO_WRITE, SafetyReason.MISSING_COMMAND_ID, None
            )
        prior = self.memory.observed.get(proposal.command_id)
        if prior is not None:
            if prior[0] == proposal.fingerprint:
                decision, command = prior[1], prior[2]
                return decision, command
            return self._finish(
                proposal,
                GuardOutcome.REJECT_NO_WRITE,
                SafetyReason.CONFLICTING_DUPLICATE,
                None,
                remember=False,
            )
        if proposal.run_id != self.memory.run_id:
            return self._finish(
                proposal, GuardOutcome.REJECT_NO_WRITE, SafetyReason.WRONG_RUN_ID, None
            )
        if (
            proposal.environment_id != self.memory.environment_id
            or proposal.environment_type not in self.settings.permitted_environments
        ):
            return self._finish(
                proposal, GuardOutcome.REJECT_NO_WRITE, SafetyReason.WRONG_ENVIRONMENT, None
            )
        if proposal.source_state_sequence < self.memory.last_valid_state_sequence:
            return self._finish(
                proposal, GuardOutcome.RESET_TO_NATIVE, SafetyReason.NON_MONOTONIC_STATE, None
            )
        if (
            proposal.source_state_sequence >= proposal.valid_from_sequence
            or proposal.source_state_sequence > proposal.decision_sequence
        ):
            return self._finish(
                proposal, GuardOutcome.REJECT_NO_WRITE, SafetyReason.FUTURE_STATE, None
            )
        if proposal.current_sequence < proposal.valid_from_sequence:
            return self._finish(
                proposal, GuardOutcome.REJECT_NO_WRITE, SafetyReason.COMMAND_FROM_FUTURE, None
            )
        if proposal.current_sequence > proposal.expires_after_sequence:
            return self._recover(proposal, SafetyReason.EXPIRED_COMMAND)
        if (
            proposal.current_sequence - proposal.source_state_sequence
            > self.settings.maximum_state_age + 1
        ):
            return self._recover(proposal, SafetyReason.STALE_STATE)
        identity_reason = self._identity_reason(proposal)
        if identity_reason is not None:
            return self._finish(proposal, GuardOutcome.REJECT_NO_WRITE, identity_reason, None)
        if proposal.reset_required:
            return self._finish(
                proposal, GuardOutcome.RESET_TO_NATIVE, SafetyReason.ALLOWED_NATIVE_RESET, None
            )
        invalid = numeric_reason(proposal.requested_value)
        if invalid is not None:
            return self._recover(proposal, invalid)
        value = proposal.requested_value
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            return self._recover(proposal, SafetyReason.NON_NUMERIC_VALUE)
        requested = float(value)
        if requested < self.settings.minimum or requested > self.settings.maximum:
            boundary = min(max(requested, self.settings.minimum), self.settings.maximum)
            if abs(requested - boundary) <= self.settings.marginal_clamp:
                return self._finish(
                    proposal, GuardOutcome.CLAMP, SafetyReason.CLAMPED_ABSOLUTE_BOUND, boundary
                )
            return self._recover(proposal, SafetyReason.OUT_OF_ABSOLUTE_BOUNDS)
        previous = self.memory.last_safe
        if previous is not None and previous.applied_value is not None:
            elapsed = max(1, proposal.source_state_sequence - previous.source_state_sequence)
            permitted = min(
                self.settings.maximum_step, self.settings.maximum_step_per_timestep * elapsed
            )
            delta = requested - previous.applied_value
            if abs(delta) > permitted:
                applied = previous.applied_value + (permitted if delta > 0 else -permitted)
                return self._finish(
                    proposal, GuardOutcome.CLAMP, SafetyReason.CLAMPED_RATE_LIMIT, applied
                )
        return self._finish(proposal, GuardOutcome.ALLOW, SafetyReason.ALLOWED, requested)

    def _identity_reason(self, proposal: ProposedCommand) -> SafetyReason | None:
        if proposal.zone in self.settings.plenum_zones:
            return SafetyReason.PLENUM_ZONE_REJECTED
        if proposal.zone not in self.settings.approved_zones:
            return SafetyReason.UNAPPROVED_ZONE
        expected, actual = self.settings.actuator, proposal.actuator
        if actual.component_type != expected.component_type:
            return SafetyReason.UNAPPROVED_COMPONENT_TYPE
        if actual.control_type != expected.control_type:
            return SafetyReason.UNAPPROVED_CONTROL_TYPE
        if actual.unique_key != expected.unique_key:
            return SafetyReason.UNAPPROVED_ACTUATOR_KEY
        if actual.units != expected.units:
            return SafetyReason.UNIT_MISMATCH
        return None

    def _recover(
        self, proposal: ProposedCommand, reason: SafetyReason
    ) -> tuple[GuardDecision, GuardedCommand | None]:
        last = self.memory.last_safe
        if last is not None and proposal.current_sequence <= last.expires_after_sequence:
            return self._finish(
                proposal,
                GuardOutcome.HOLD_LAST_SAFE,
                SafetyReason.HELD_LAST_SAFE,
                last.applied_value,
                (reason,),
            )
        return self._finish(proposal, GuardOutcome.RESET_TO_NATIVE, reason, None, (reason,))

    def _finish(
        self,
        proposal: ProposedCommand,
        outcome: GuardOutcome,
        reason: SafetyReason,
        applied: float | None,
        violations: tuple[SafetyReason, ...] = (),
        *,
        remember: bool = True,
    ) -> tuple[GuardDecision, GuardedCommand | None]:
        decision_id = canonical_hash(
            {
                "proposal": proposal.fingerprint,
                "outcome": outcome,
                "reason": reason,
                "applied": applied,
            }
        )
        decision = GuardDecision(
            decision_id,
            proposal.command_id,
            proposal.run_id,
            proposal.environment_id,
            outcome,
            reason,
            proposal.requested_value,
            applied,
            None if self.memory.last_safe is None else self.memory.last_safe.applied_value,
            proposal.source_state_sequence,
            proposal.current_sequence,
            self.settings.schema_version,
            violations,
        )
        command = (
            None
            if outcome == GuardOutcome.REJECT_NO_WRITE
            else make_guarded_command(proposal, decision)
        )
        if self.persist is not None:
            try:
                self.persist(decision, command)
            except Exception as exc:
                self.persistence_failures += 1
                self.last_persistence_error = f"{type(exc).__name__}: {exc}"
                failed = GuardDecision(
                    canonical_hash({"failed": decision_id}),
                    proposal.command_id,
                    proposal.run_id,
                    proposal.environment_id,
                    GuardOutcome.REJECT_NO_WRITE,
                    SafetyReason.PERSISTENCE_FAILURE_FAIL_CLOSED,
                    proposal.requested_value,
                    None,
                    decision.previous_safe_value,
                    proposal.source_state_sequence,
                    proposal.current_sequence,
                    self.settings.schema_version,
                    (SafetyReason.PERSISTENCE_FAILURE_FAIL_CLOSED,),
                )
                return failed, None
        if remember:
            self.memory.last_proposal, self.memory.last_decision = proposal, decision
            self.memory.last_valid_state_sequence = max(
                self.memory.last_valid_state_sequence, proposal.source_state_sequence
            )
            self.memory.observed[proposal.command_id] = (proposal.fingerprint, decision, command)
            if command is not None and outcome in {
                GuardOutcome.ALLOW,
                GuardOutcome.CLAMP,
                GuardOutcome.HOLD_LAST_SAFE,
            }:
                self.memory.last_safe = command
        return decision, command
