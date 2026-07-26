"""Deterministic dashboard claim policy."""

from __future__ import annotations

from src.dashboard.models import ClaimClassification

PROHIBITED_CLAIMS = ("annual savings achieved", "guaranteed comfort", "real-building savings")


def validate_claim(text: str, classification: ClaimClassification) -> None:
    lowered = text.lower()
    if any(item in lowered for item in PROHIBITED_CLAIMS):
        raise ValueError("unsupported_claim")
    if "rtfu" in lowered and ("kwh" in lowered or "physical energy" in lowered):
        raise ValueError("physical_energy_proxy_claim")
    if (
        classification == ClaimClassification.NOT_ESTABLISHED
        and "established" in lowered
        and "not established" not in lowered
    ):
        raise ValueError("not_established_claim_overstated")
