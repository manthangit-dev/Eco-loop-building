"""Construct trusted live-timed proposals from bound plan actions."""

from src.control.models import ActuatorIdentity
from src.execution.models import ScheduledAction, TrustedLiveState
from src.planning.provenance import planning_fingerprint
from src.safety.models import ProposedCommand


def build_proposal(
    action: ScheduledAction, state: TrustedLiveState, actuator: ActuatorIdentity, ttl: int
) -> ProposedCommand:
    command_id = planning_fingerprint(
        {"session": state.execution_session_id, "action": action.plan_action_id}
    )
    return ProposedCommand(
        command_id=command_id,
        decision_id=action.plan_action_id,
        run_id=state.run_id,
        environment_id=state.environment_id,
        zone=actuator.unique_key,
        actuator=actuator,
        requested_value=action.requested_value,
        source_state_sequence=state.current_sequence - 1,
        decision_sequence=state.current_sequence - 1,
        valid_from_sequence=state.current_sequence,
        expires_after_sequence=state.current_sequence + ttl,
        current_sequence=state.current_sequence,
        source_simulation_time_hours=state.simulation_time_hours - 0.25,
        decision_simulation_time_hours=state.simulation_time_hours - 0.25,
        callback_simulation_time_hours=state.simulation_time_hours,
        api_ready=state.api_ready,
        warmup=state.warmup,
    )


def build_reset_proposal(
    state: TrustedLiveState, actuator: ActuatorIdentity, ttl: int
) -> ProposedCommand:
    action = ScheduledAction(
        plan_action_id="mandatory-native-reset",
        action_sequence=state.current_plan_action_index + 1,
        timestep_offset=state.current_plan_action_index + 1,
        intended_simulation_timestamp=state.current_simulation_timestamp,
        earliest_timestep=state.current_plan_action_index + 1,
        latest_timestep=state.current_plan_action_index + 1,
        requested_value=22.0,
        units="C",
        action_type="RESET",
    )
    proposal = build_proposal(action, state, actuator, ttl)
    return ProposedCommand(**{**proposal.__dict__, "reset_required": True})
