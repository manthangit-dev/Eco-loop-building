"""Module 7 test helpers."""

from dataclasses import replace

from src.control.config import FallbackSettings, load_fallback_settings
from src.state.models import BuildingState

from tests.state_helpers import ROOT, sample_state


def settings() -> FallbackSettings:
    return load_fallback_settings(ROOT / "config/fallback_controller.yaml", ROOT)


def control_state(
    *,
    sequence: int = 1,
    zone_name: str = "SPACE3-1",
    occupancy: float = 1.0,
    temperature: float = 24.0,
    setpoint: float | None = 23.9,
) -> BuildingState:
    state = sample_state(sequence=sequence)
    zones = tuple(
        replace(
            zone,
            occupant_count=occupancy if zone.exact_name == zone_name else zone.occupant_count,
            mean_air_temperature_c=temperature
            if zone.exact_name == zone_name
            else zone.mean_air_temperature_c,
            effective_cooling_setpoint_c=setpoint if zone.exact_name == zone_name else None,
        )
        for zone in state.zones
    )
    return replace(state, zones=zones, fingerprint=f"{sequence:064x}")
