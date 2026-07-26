"""Observed post-command diagnostic outcomes."""

from src.control.models import CommandOutcome, ControlCommand, deterministic_hash
from src.state.models import BuildingState


def observe_command(command: ControlCommand, state: BuildingState) -> CommandOutcome | None:
    if state.sequence <= command.issued_from_sequence:
        return None
    zone = next((item for item in state.zones if item.zone_id == command.target_zone_id), None)
    if zone is None:
        return None
    payload = {"command": command.command_id, "state": state.sequence, "event": "OBSERVED"}
    return CommandOutcome(
        outcome_id=deterministic_hash(payload),
        command_id=command.command_id,
        observed_state_sequence=state.sequence,
        event_type="OBSERVED",
        effective_setpoint_celsius=zone.effective_cooling_setpoint_c,
        zone_temperature_celsius=zone.mean_air_temperature_c,
        occupancy=zone.occupant_count,
        outdoor_temperature_celsius=state.outdoor.dry_bulb_c,
        facility_electricity_raw_j=state.building_energy.facility_purchased_electricity_raw_j,
        hvac_electricity_raw_j=state.building_energy.hvac_electricity_raw_j,
    )
