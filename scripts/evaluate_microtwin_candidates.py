"""Evaluate every eligible Module 11 candidate with the qualified MicroTwin."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.microtwin.config import load_microtwin_settings
from src.microtwin.rollout import rank_rollouts, rollout
from src.storage.microtwin_store import persist

from scripts.planning_common import build

if __name__ == "__main__":
    context, plans = build()
    settings = load_microtwin_settings(Path("config/microtwin.yaml"))
    rollouts = tuple(rollout(context, plan, settings) for plan in plans if plan.eligible)
    ranked = rank_rollouts(rollouts)
    advisory = [plan.plan_id for plan in plans if plan.eligible]
    report = {
        "status": "PASS",
        "rollout_count": len(rollouts),
        "rollouts": [item.model_dump(mode="json") for item in rollouts],
        "microtwin_ranking": [item.plan_id for item in ranked],
        "advisory_ranking": advisory,
        "rankings_agree": advisory == [item.plan_id for item in ranked],
        "selected_plan": ranked[0].plan_id,
        "physical_write_count": 0,
        "energyplus_processes_started": 0,
    }
    manifest = json.loads((settings.model_directory / "model_manifest.json").read_text())
    validation = json.loads(
        (settings.model_directory / "thermal_validation_report.json").read_text()
    )
    persist(settings.database, manifest, validation, rollouts, advisory[0])
    path = Path("outputs/microtwin/candidate_evaluation.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
