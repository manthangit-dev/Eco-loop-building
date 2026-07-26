"""Simulation-only approval-gated execution orchestrator."""

from __future__ import annotations

import time
from typing import Protocol

from scripts.planning_common import build

from src.execution.approval import validate_approval
from src.execution.command_builder import build_proposal, build_reset_proposal
from src.execution.config import ExecutionSettings
from src.execution.live_state import validate_live_state
from src.execution.models import (
    ActionOutcome,
    ExecutionApproval,
    ExecutionMode,
    ExecutionReport,
    ExecutionState,
    TrustedLiveState,
)
from src.execution.preflight import resolve_execution_binding
from src.execution.scheduler import ActionScheduler
from src.execution.state_machine import ExecutionStateMachine
from src.safety.config import load_safety_settings
from src.safety.guard import SafetyGuard
from src.safety.memory import SafetyMemory
from src.safety.models import GuardedCommand, GuardOutcome


class ExecutionWriter(Protocol):
    def submit(self, command: GuardedCommand) -> str: ...

    def reset(self, command: GuardedCommand) -> str: ...


class FakeWriter:
    def __init__(self, physical: bool = False, fail: bool = False) -> None:
        self.physical = physical
        self.fail = fail
        self.set_calls = 0
        self.reset_calls = 0

    def submit(self, command: GuardedCommand) -> str:
        if self.fail:
            raise RuntimeError("fake_writer_failure")
        if self.physical:
            self.set_calls += 1
        return "SUBMITTED" if self.physical else "DRY_RUN"

    def reset(self, command: GuardedCommand) -> str:
        if self.fail:
            raise RuntimeError("fake_reset_failure")
        if self.physical:
            self.reset_calls += 1
        return "RESET" if self.physical else "DRY_RUN_RESET"


class ExecutionOrchestrator:
    def __init__(self, settings: ExecutionSettings, writer: ExecutionWriter) -> None:
        self.settings, self.writer = settings, writer

    def execute(
        self,
        approval: ExecutionApproval,
        mode: ExecutionMode,
        live_states: tuple[TrustedLiveState, ...],
    ) -> ExecutionReport:
        started = time.monotonic()
        binding = resolve_execution_binding(self.settings, approval.selected_plan_id)
        validate_approval(approval, binding, self.settings, mode)
        context, plans = build()
        plan = next(item for item in plans if item.plan_id == approval.selected_plan_id)
        machine = ExecutionStateMachine()
        machine.transition(ExecutionState.PREFLIGHT, "preflight_started")
        machine.transition(ExecutionState.APPROVAL_REQUIRED, "approval_required")
        machine.transition(ExecutionState.ARMED, "approval_valid")
        machine.transition(ExecutionState.WAITING_FOR_LIVE_STATE, "awaiting_committed_state")
        scheduler = ActionScheduler(
            plan, approval.allowed_action_count, self.settings.minimum_hold_timesteps
        )
        safety = load_safety_settings(self.settings.root / "config/safety_guard.yaml")
        memory = SafetyMemory(context.run_id, context.environment_id)
        guard = SafetyGuard(safety, memory)
        outcomes: list[ActionOutcome] = []
        fallback = 0
        machine.transition(ExecutionState.EXECUTING, "live_state_ready")
        last_state = live_states[-1]
        try:
            for state in live_states:
                validate_live_state(
                    state, approval.permitted_environment, approval.actuator_identity
                )
                action = scheduler.due(state.current_plan_action_index + 1)
                if action is None:
                    continue
                proposal = build_proposal(action, state, safety.actuator, safety.command_ttl)
                decision, command = guard.evaluate(proposal)
                if command is None:
                    outcomes.append(
                        ActionOutcome(
                            action=action,
                            guard_outcome=decision.outcome.value,
                            guard_reason=decision.reason.value,
                            guarded_value=None,
                            writer_status="NOT_WRITTEN",
                            terminal_status="REJECTED",
                            physical_write=False,
                        )
                    )
                    fallback += 1
                    machine.transition(ExecutionState.FALLBACK_ACTIVE, "guard_rejection")
                    break
                status = self.writer.submit(command)
                scheduler.complete(action)
                outcomes.append(
                    ActionOutcome(
                        action=action,
                        guard_outcome=decision.outcome.value,
                        guard_reason=decision.reason.value,
                        guarded_value=command.applied_value,
                        writer_status=status,
                        terminal_status="COMPLETED",
                        physical_write=mode == ExecutionMode.LIVE_SHORT_HORIZON,
                    )
                )
                machine.transition(ExecutionState.HOLDING, "minimum_hold")
                machine.transition(ExecutionState.EXECUTING, "hold_complete")
        except Exception:
            fallback += 1
            if machine.state not in {
                ExecutionState.FALLBACK_ACTIVE,
                ExecutionState.RESETTING_TO_NATIVE,
            }:
                machine.transition(ExecutionState.FALLBACK_ACTIVE, "execution_failure")
        machine.transition(ExecutionState.RESETTING_TO_NATIVE, "mandatory_native_reset")
        reset = build_reset_proposal(last_state, safety.actuator, safety.command_ttl)
        reset_decision, reset_command = guard.evaluate(reset)
        reset_ok = (
            reset_command is not None and reset_decision.outcome == GuardOutcome.RESET_TO_NATIVE
        )
        if reset_command is not None:
            try:
                self.writer.reset(reset_command)
            except Exception:
                reset_ok = False
        final = ExecutionState.COMPLETED if reset_ok and not fallback else ExecutionState.ABORTED
        machine.transition(final, "reset_complete" if reset_ok else "reset_failed")
        return ExecutionReport(
            status="PASS" if final == ExecutionState.COMPLETED else "FAIL",
            session_id=live_states[0].execution_session_id,
            approval_id=approval.approval_id,
            mode=mode,
            final_state=final,
            transitions=tuple(machine.transitions),
            actions=tuple(outcomes),
            scheduled_action_count=len(scheduler.actions),
            executed_action_count=len(scheduler.completed),
            skipped_action_count=len(scheduler.actions) - len(scheduler.completed),
            duplicate_action_count=0,
            physical_set_calls=getattr(self.writer, "set_calls", 0),
            physical_reset_calls=getattr(self.writer, "reset_calls", 0),
            fallback_activation_count=fallback,
            mandatory_native_reset=reset_ok,
            unguarded_write_count=0,
            runtime_seconds=round(time.monotonic() - started, 3),
        )
