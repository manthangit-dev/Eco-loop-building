"""Transactional, idempotent persistence for Module 13 advisory evidence."""

# ruff: noqa: E501

from __future__ import annotations

import json
import sqlite3

from src.ledger.models import LedgerPlanEvaluation, LedgerRanking
from src.planning.provenance import planning_fingerprint
from src.storage.ledger_schema import migrate


class LedgerStore:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection
        migrate(connection)

    def persist(
        self, evaluations: tuple[LedgerPlanEvaluation, ...], ranking: LedgerRanking, zone: str
    ) -> None:
        account_id = planning_fingerprint({"zone": zone, "ledger": 1})
        bank_id = planning_fingerprint({"zone": zone, "bank": 1})
        account_fp = planning_fingerprint({"account": account_id, "opening": 0})
        bank_fp = planning_fingerprint({"account": bank_id, "opening": 0, "unit": "RTFU"})
        try:
            self.connection.execute("BEGIN")
            self.connection.execute(
                "INSERT OR IGNORE INTO comfort_ledger_accounts VALUES(?,?,?,?,?,?,?,?,?)",
                (account_id, zone, 1, "ACTIVE", 0, 0.0, 0.0, "NONE", account_fp),
            )
            self.connection.execute(
                "INSERT OR IGNORE INTO thermal_bank_accounts VALUES(?,?,?,?,?,?,?,?)",
                (bank_id, zone, "RTFU", "ACTIVE", 0, 0.0, 1, bank_fp),
            )
            transaction_sequence = 1
            for evaluation in evaluations:
                for entry in evaluation.entries:
                    self.connection.execute(
                        "INSERT OR IGNORE INTO comfort_ledger_entries VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (
                            entry.entry_id,
                            account_id,
                            entry.context_id,
                            entry.plan_id,
                            entry.rollout_id,
                            entry.event_id,
                            entry.timestep,
                            entry.simulation_timestamp,
                            entry.entry_type,
                            entry.evidence_type,
                            entry.occupancy,
                            entry.lower_boundary_c,
                            entry.upper_boundary_c,
                            entry.predicted_temperature_c,
                            entry.lower_uncertainty_c,
                            entry.upper_uncertainty_c,
                            entry.total_burden,
                            entry.credit,
                            entry.debt,
                            entry.repayment,
                            ",".join(entry.reason_codes),
                            entry.fingerprint,
                        ),
                    )
                fairness = evaluation.fairness
                self.connection.execute(
                    "INSERT OR IGNORE INTO comfort_fairness_assessments VALUES(?,?,?,?,?,?,?,?,?)",
                    (
                        fairness.assessment_id,
                        fairness.context_id,
                        fairness.plan_id,
                        json.dumps({"maximum_event_burden": fairness.maximum_event_burden}),
                        json.dumps(
                            {
                                "concentration": fairness.burden_concentration_ratio,
                                "variance": fairness.temporal_burden_variance,
                            }
                        ),
                        evaluation.comfort_equity_score,
                        fairness.status,
                        json.dumps(fairness.reason_codes),
                        fairness.fingerprint,
                    ),
                )
                burden_entry = next((entry for entry in evaluation.entries if entry.debt > 0), None)
                if burden_entry is not None:
                    debt_id = planning_fingerprint({"debt": evaluation.evaluation_id})
                    self.connection.execute(
                        "INSERT OR IGNORE INTO comfort_debt_records VALUES(?,?,?,?,?,?,?,?,?,?)",
                        (
                            debt_id,
                            account_id,
                            burden_entry.entry_id,
                            evaluation.new_comfort_burden,
                            evaluation.closing_comfort_debt,
                            burden_entry.simulation_timestamp,
                            0,
                            evaluation.debt_status,
                            evaluation.recovery_obligation,
                            None,
                        ),
                    )
                components = (
                    ("DEPOSIT", evaluation.bank.deposit),
                    ("WITHDRAWAL", evaluation.bank.withdrawal),
                    ("UNCERTAINTY_RESERVE", evaluation.bank.uncertainty_reserve),
                    ("PROTECTED_EVENT_RESERVE", evaluation.bank.protected_event_reserve),
                    ("DEBT_PENALTY", evaluation.bank.debt_penalty),
                )
                opening = evaluation.bank.opening_balance
                for transaction_type, amount in components:
                    if amount == 0:
                        continue
                    transaction_id = planning_fingerprint(
                        {"evaluation": evaluation.evaluation_id, "type": transaction_type}
                    )
                    closing = evaluation.bank.closing_balance
                    fingerprint = planning_fingerprint(
                        {"transaction": transaction_id, "amount": amount, "closing": closing}
                    )
                    self.connection.execute(
                        "INSERT OR IGNORE INTO thermal_bank_transactions VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (
                            transaction_id,
                            bank_id,
                            transaction_sequence,
                            evaluation.entries[0].simulation_timestamp,
                            transaction_type,
                            amount,
                            opening,
                            closing,
                            evaluation.plan_id,
                            evaluation.rollout_id,
                            None,
                            None,
                            "advisory_plan_evaluation",
                            fingerprint,
                        ),
                    )
                    transaction_sequence += 1
                self.connection.execute(
                    "INSERT OR IGNORE INTO ledger_plan_evaluations VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        evaluation.evaluation_id,
                        evaluation.context_id,
                        evaluation.plan_id,
                        evaluation.rollout_id,
                        evaluation.new_comfort_burden,
                        evaluation.comfort_credit,
                        evaluation.opening_comfort_debt,
                        evaluation.closing_comfort_debt,
                        evaluation.comfort_equity_score,
                        evaluation.bank.opening_balance,
                        evaluation.bank.deposit,
                        evaluation.bank.withdrawal,
                        evaluation.bank.uncertainty_reserve
                        + evaluation.bank.protected_event_reserve,
                        evaluation.bank.closing_balance,
                        evaluation.advisory_score,
                        evaluation.microtwin_score,
                        evaluation.ledger_aware_score,
                        int(evaluation.eligible),
                        json.dumps(evaluation.rejection_reasons),
                        0,
                        evaluation.fingerprint,
                        evaluation.model_dump_json(),
                    ),
                )
            self.connection.execute(
                "INSERT OR IGNORE INTO ledger_rankings VALUES(?,?,?,?,?,?,?,?,?,?)",
                (
                    ranking.ranking_id,
                    ranking.context_id,
                    json.dumps(ranking.module13_ranking),
                    json.dumps(ranking.module11_ranking),
                    json.dumps(ranking.module12_ranking),
                    json.dumps(ranking.module13_ranking),
                    int(ranking.rankings_all_agree),
                    ranking.selected_plan_id,
                    0,
                    ranking.fingerprint,
                ),
            )
            self.connection.commit()
        except Exception:
            self.connection.rollback()
            raise
