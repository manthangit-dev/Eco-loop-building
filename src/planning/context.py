"""Build canonical planning context from one committed state and local scenarios."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from src.planning.config import PlanningSettings
from src.planning.forecast import checksum, load_events, load_points
from src.planning.models import PlanningContext
from src.planning.provenance import planning_fingerprint


def build_context(
    settings: PlanningSettings,
    run_id: str,
    state_database: Path,
    source_state_id: int,
    environment_id: str,
    zone: str = "SPACE3-1",
    horizon: int | None = None,
) -> PlanningContext:
    horizon = horizon or settings.default_horizon
    if not settings.minimum_horizon <= horizon <= settings.maximum_horizon:
        raise ValueError("horizon outside configured bounds")
    if zone not in settings.allowed_zones:
        raise ValueError("unapproved planning zone")
    connection = sqlite3.connect(f"file:{state_database.resolve()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    row = connection.execute(
        """SELECT b.sequence,b.month,b.day,b.hour,b.minute,b.environment_number,
        z.mean_air_temperature_c,z.effective_cooling_setpoint_c,z.occupant_count
        FROM building_states b JOIN zone_states z ON z.building_state_id=b.id
        WHERE b.sequence=? AND z.exact_name=?""",
        (source_state_id, zone),
    ).fetchone()
    connection.close()
    if row is None or f"weather-{row['environment_number']}" != environment_id:
        raise ValueError("committed state/environment unavailable")
    timestamp = f"{row['month']:02}-{row['day']:02} {row['hour']:02}:{row['minute']:02}"
    forecasts = tuple(
        point
        for kind in ("weather", "occupancy", "tariff", "carbon")
        for point in load_points(settings.sources[kind], kind, environment_id, zone)
    )
    if not forecasts:
        raise ValueError("forecast context is empty")
    sources = {name: checksum(path) for name, path in settings.sources.items()}
    identity = "Zone Temperature Control|Cooling Setpoint|SPACE3-1|C"
    context_id = planning_fingerprint(
        {
            "run": run_id,
            "state": source_state_id,
            "zone": zone,
            "horizon": horizon,
            "sources": sources,
        }
    )
    return PlanningContext(
        context_id=context_id,
        run_id=run_id,
        environment_id=environment_id,
        source_state_id=source_state_id,
        planning_timestamp=timestamp,
        target_zone=zone,
        actuator_identity=identity,
        current_zone_temperature_c=float(row["mean_air_temperature_c"]),
        current_effective_setpoint_c=row["effective_cooling_setpoint_c"],
        current_occupancy=float(row["occupant_count"]),
        current_controller_mode=None,
        current_safety_status="ENABLED_FAIL_CLOSED",
        horizon=horizon,
        timestep_minutes=settings.timestep_minutes,
        forecasts=forecasts,
        events=load_events(settings.sources["events"], environment_id, zone),
        source_checksums=sources,
    )
