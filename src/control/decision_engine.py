"""Canonical-state to deterministic decision/command engine."""

from __future__ import annotations

from dataclasses import replace

from src.control.config import FallbackSettings
from src.control.controller_memory import ControllerMemory
from src.control.fallback_policy import evaluate_zone
from src.control.models import ControlCommand, ControlDecision, deterministic_hash
from src.control.reason_codes import ActionType, DecisionReason
from src.state.models import BuildingState, NonMonotonicSequenceError


class FallbackDecisionEngine:
    def __init__(self, run_id: str, settings: FallbackSettings, *, shadow: bool) -> None:
        self.run_id = run_id
        self.settings = settings
        self.shadow = shadow
        self.memory = ControllerMemory(run_id)
        self._last_sequence = 0
        self.decision_count = 0

    def evaluate(
        self, state: BuildingState
    ) -> tuple[tuple[ControlDecision, ControlCommand | None], ...]:
        if state.sequence <= self._last_sequence:
            raise NonMonotonicSequenceError("Controller state sequence did not progress.")
        gap = state.sequence - self._last_sequence if self._last_sequence else 1
        results: list[tuple[ControlDecision, ControlCommand | None]] = []
        zones = tuple(
            zone
            for zone in state.zones
            if not zone.is_plenum and (self.shadow or zone.exact_name == self.settings.real_zone)
        )
        for zone in sorted(zones, key=lambda item: item.zone_id):
            before = self.memory.get(zone.zone_id)
            if gap > self.settings.maximum_sequence_gap:
                policy = evaluate_zone(zone, before, self.settings, state.sequence)
                policy = replace(
                    policy,
                    reason=DecisionReason.REJECT_STALE_STATE,
                    action=ActionType.RESET,
                    requested=None,
                    approved=None,
                    explanation="State sequence gap exceeded configured maximum.",
                )
            else:
                policy = evaluate_zone(zone, before, self.settings, state.sequence)
            self.memory.update(policy.memory)
            self.decision_count += 1
            stable = {
                "run_mode": "shadow" if self.shadow else "live_control",
                "decision_sequence": self.decision_count,
                "state_sequence": state.sequence,
                "state_fingerprint": state.fingerprint,
                "zone": zone.zone_id,
                "before": before.current_mode.value,
                "after": policy.mode.value,
                "reason": policy.reason.value,
                "action": policy.action.value,
                "requested": policy.requested,
                "approved": policy.approved,
                "ttl": self.settings.command_ttl,
            }
            decision_id = deterministic_hash(stable)
            decision = ControlDecision(
                decision_id=decision_id,
                run_id=self.run_id,
                decision_sequence=self.decision_count,
                based_on_state_sequence=state.sequence,
                based_on_state_fingerprint=state.fingerprint,
                created_at_utc=state.captured_at_utc,
                target_zone_id=zone.zone_id,
                target_zone_name=zone.exact_name,
                controller_mode_before=before.current_mode,
                controller_mode_after=policy.mode,
                reason_code=policy.reason,
                explanation=policy.explanation,
                occupancy=zone.occupant_count,
                zone_temperature_celsius=zone.mean_air_temperature_c,
                baseline_setpoint_celsius=policy.baseline,
                requested_setpoint_celsius=policy.requested,
                approved_setpoint_celsius=policy.approved,
                clamped=policy.clamped,
                action_type=policy.action,
                command_ttl=self.settings.command_ttl,
                intended_effective_sequence=state.sequence + 1,
                actuator=replace(self.settings.actuator, unique_key=zone.exact_name),
                shadow_mode=self.shadow,
            )
            command = self._command(decision)
            results.append((decision, command))
        self._last_sequence = state.sequence
        return tuple(results)

    def _command(self, decision: ControlDecision) -> ControlCommand | None:
        if decision.action_type not in {ActionType.APPLY_SETPOINT, ActionType.RESET}:
            return None
        reset = decision.action_type is ActionType.RESET
        payload = {
            "decision_id": decision.decision_id,
            "zone": decision.target_zone_id,
            "actuator": decision.actuator.key,
            "setpoint": decision.approved_setpoint_celsius,
            "issued": decision.based_on_state_sequence,
            "valid": decision.intended_effective_sequence,
            "expires": decision.based_on_state_sequence + self.settings.command_ttl,
            "reset": reset,
        }
        fingerprint = deterministic_hash(payload)
        return ControlCommand(
            command_id=fingerprint,
            decision_id=decision.decision_id,
            target_zone_id=decision.target_zone_id,
            target_zone_name=decision.target_zone_name,
            actuator=decision.actuator,
            setpoint_celsius=decision.approved_setpoint_celsius,
            issued_from_sequence=decision.based_on_state_sequence,
            valid_from_sequence=decision.intended_effective_sequence,
            expires_after_sequence=decision.based_on_state_sequence + self.settings.command_ttl,
            reset_required=reset,
            mode=decision.controller_mode_after,
            reason=decision.reason_code,
            shadow_mode=decision.shadow_mode,
            fingerprint=fingerprint,
        )
