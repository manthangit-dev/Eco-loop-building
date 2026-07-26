"""Shared deterministic Module 11 construction."""


from src.planning.config import load_planning_settings
from src.planning.context import build_context
from src.planning.generator import generate_plans
from src.planning.models import CandidatePlan, PlanningContext
from src.storage.planning_store import PlanningStore

from scripts.demo_common import ROOT, select_demo_run


def build() -> tuple[PlanningContext, tuple[CandidatePlan, ...]]:
    selected = select_demo_run()
    settings = load_planning_settings(ROOT / "config/planning.yaml")
    state_db = ROOT / selected["state_database"]
    context = build_context(
        settings, selected["run_id"], state_db, 19345, selected["environment_id"]
    )
    plans = generate_plans(context, settings)
    with PlanningStore(settings.database, settings.output_root) as store:
        store.persist(context, plans)
    return context, plans
