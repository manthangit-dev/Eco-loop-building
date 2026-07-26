import json
import sqlite3
from pathlib import Path

from src.microtwin.rollout import PlanRollout
from src.planning.provenance import planning_fingerprint
from src.storage.microtwin_schema import migrate


def persist(
    database: Path,
    manifest: dict[str, object],
    validation: dict[str, object],
    rollouts: tuple[PlanRollout, ...],
    advisory_selected: str,
) -> None:
    database.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(database)
    migrate(c)
    model_id = str(manifest["model_id"])
    c.execute(
        "INSERT OR REPLACE INTO microtwin_models VALUES(?,?,?,?,?,?,0)",
        (
            model_id,
            "QUALIFIED",
            "deterministic_ridge_arx",
            manifest["semantic_fingerprint"],
            json.dumps(validation, sort_keys=True),
            "QUALIFIED" if manifest["demand_qualification"] else "UNAVAILABLE",
        ),
    )
    for item in rollouts:
        c.execute(
            "INSERT OR REPLACE INTO microtwin_rollouts VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (
                item.rollout_id,
                model_id,
                item.plan_id,
                item.context_id,
                item.qualification_status,
                item.microtwin_score,
                item.advisory_score,
                item.ood_feature_count,
                0,
                item.rollout_fingerprint,
                item.model_dump_json(),
            ),
        )
        for point in item.points:
            c.execute(
                "INSERT OR REPLACE INTO microtwin_rollout_points VALUES(?,?,?,?,?,?,?,?,?)",
                (
                    item.rollout_id,
                    point.timestep,
                    point.predicted_temperature_c,
                    point.lower_temperature_c,
                    point.upper_temperature_c,
                    point.setpoint_c,
                    point.expected_occupancy,
                    point.outdoor_temperature_c,
                    int(point.occupied_boundary_risk),
                ),
            )
    ranked = sorted(rollouts, key=lambda item: (item.microtwin_score, item.plan_id))
    payload = {
        "ranking": [item.plan_id for item in ranked],
        "selected": ranked[0].plan_id,
        "advisory_selected": advisory_selected,
    }
    ranking_id = planning_fingerprint({"model": model_id, **payload})
    c.execute(
        "INSERT OR REPLACE INTO microtwin_rankings VALUES(?,?,?,?,?,?,?,?,?)",
        (
            ranking_id,
            model_id,
            rollouts[0].context_id,
            ranked[0].plan_id,
            advisory_selected,
            int(ranked[0].plan_id == advisory_selected),
            "COMPLETED",
            0,
            json.dumps(payload, sort_keys=True),
        ),
    )
    c.commit()
    c.close()
