"""Claim boundary for read-only execution explanations."""

from __future__ import annotations


class ExecutionClaimError(ValueError):
    pass


FORBIDDEN = {
    "real building": "false_real_building_claim",
    "annual savings": "false_annual_savings_claim",
    "guaranteed comfort": "false_guaranteed_comfort_claim",
    "i initiated": "false_llm_execution_claim",
    "i executed": "false_llm_execution_claim",
}


def validate_execution_response(text: str) -> None:
    lowered = text.lower()
    for phrase, reason in FORBIDDEN.items():
        if phrase in lowered:
            raise ExecutionClaimError(reason)
