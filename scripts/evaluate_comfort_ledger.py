"""Evaluate and serialize every qualified Module 12 rollout through Module 13."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.ledger.config import load_comfort_ledger_settings
from src.ledger.evaluation import evaluate_candidates, rank_evaluations
from src.microtwin.config import load_microtwin_settings
from src.microtwin.rollout import rollout
from src.storage.ledger_store import LedgerStore
from src.thermal_bank.config import load_thermal_bank_settings

from scripts.planning_common import build

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "outputs/ledger/evaluations.json")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    started = time.monotonic()
    context, plans = build()
    micro = load_microtwin_settings(ROOT / "config/microtwin.yaml")
    rollouts = tuple(rollout(context, plan, micro) for plan in plans if plan.eligible)
    ledger = load_comfort_ledger_settings(ROOT / "config/comfort_ledger.yaml")
    bank = load_thermal_bank_settings(ROOT / "config/thermal_bank.yaml")
    evaluations = evaluate_candidates(context, plans, rollouts, ledger, bank)
    ranking = rank_evaluations(context, plans, rollouts, evaluations)
    with sqlite3.connect(micro.database) as connection:
        LedgerStore(connection).persist(evaluations, ranking, context.target_zone)
    report = {
        "status": "PASS",
        "initial_state": {
            "comfort_credit": 0,
            "comfort_debt": 0,
            "debt_status": "NONE",
            "thermal_bank_balance_rtfu": 0,
        },
        "evaluations": [item.model_dump(mode="json") for item in evaluations],
        "ranking": ranking.model_dump(mode="json"),
        "demand_model_status": "UNAVAILABLE",
        "physical_write_count": 0,
        "runtime_seconds": round(time.monotonic() - started, 3),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2 if args.pretty else None))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
