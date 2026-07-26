"""Fail-closed Thermal Bank accounting."""

from __future__ import annotations

import math

from src.thermal_bank.config import ThermalBankSettings
from src.thermal_bank.errors import ThermalBankValidationError


def closing_balance(
    *,
    opening: float,
    deposit: float,
    withdrawal: float,
    decay: float,
    expiry: float,
    debt_penalty: float,
    uncertainty_reserve: float,
    protected_event_reserve: float,
    settings: ThermalBankSettings,
) -> float:
    values = (
        opening,
        deposit,
        withdrawal,
        decay,
        expiry,
        debt_penalty,
        uncertainty_reserve,
        protected_event_reserve,
    )
    if not all(math.isfinite(value) for value in values):
        raise ThermalBankValidationError("non_finite_bank_amount")
    if any(value < 0 for value in values):
        raise ThermalBankValidationError("negative_bank_amount")
    result = opening + deposit - withdrawal - decay - expiry - debt_penalty
    result -= uncertainty_reserve + protected_event_reserve
    if result < settings.minimum_balance and not settings.overdraft_allowed:
        raise ThermalBankValidationError("thermal_bank_overdraft")
    if result > settings.maximum_balance:
        raise ThermalBankValidationError("maximum_thermal_balance_exceeded")
    return round(result, 6)
