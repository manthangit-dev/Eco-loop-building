"""Deterministic policy validation for ledger-related model prose."""

from __future__ import annotations

import re
from collections.abc import Sequence

from src.mcp_server.models import ToolEnvelope


class LedgerClaimError(ValueError):
    def __init__(self, reason_code: str) -> None:
        self.reason_code = reason_code
        super().__init__(reason_code)


def validate_ledger_response(text: str, evidence: Sequence[ToolEnvelope]) -> None:
    lowered = text.lower()
    rules = (
        (r"(?:stored|banked).{0,20}\bkwh\b", "false_stored_kwh_claim"),
        (r"guaranteed comfort", "guaranteed_comfort_claim"),
        (r"verified (?:energy |cost |carbon )?savings?", "verified_savings_claim"),
        (r"plan (?:was|has been) executed", "false_physical_execution_claim"),
        (r"actual human discomfort", "subjective_comfort_claim"),
    )
    for pattern, reason in rules:
        if re.search(pattern, lowered):
            raise LedgerClaimError(reason)
    serialized = " ".join(result.model_dump_json() for result in evidence if result.success)
    referenced = set(re.findall(r"(?:transaction|event)_[a-f0-9]{8,64}", lowered))
    if any(value not in serialized for value in referenced):
        raise LedgerClaimError("invented_ledger_evidence")


def validate_authoritative_values(
    *,
    claimed_debt: float,
    claimed_balance: float,
    claimed_equity: float,
    actual_debt: float,
    actual_balance: float,
    actual_equity: float,
) -> None:
    if claimed_debt != actual_debt:
        raise LedgerClaimError("changed_debt_claim")
    if claimed_balance != actual_balance:
        raise LedgerClaimError("changed_bank_balance_claim")
    if claimed_equity != actual_equity:
        raise LedgerClaimError("changed_equity_score_claim")
