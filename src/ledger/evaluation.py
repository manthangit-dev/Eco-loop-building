"""Deterministic Comfort Ledger, Thermal Bank, and advisory ranking calculations."""

from __future__ import annotations

import math
from datetime import datetime, timedelta
from statistics import pvariance

from src.ledger.config import ComfortLedgerSettings
from src.ledger.errors import LedgerValidationError
from src.ledger.models import (
    ComfortFairnessAssessment,
    ComfortLedgerEntry,
    LedgerPlanEvaluation,
    LedgerRanking,
    ThermalBankSummary,
)
from src.microtwin.rollout import PlanRollout, rank_rollouts
from src.planning.models import CandidatePlan, PlanningContext
from src.planning.provenance import planning_fingerprint
from src.thermal_bank.accounting import closing_balance
from src.thermal_bank.config import ThermalBankSettings


def _debt_status(debt: float, maximum: float) -> str:
    ratio = debt / maximum
    if debt == 0:
        return "NONE"
    if ratio < 0.2:
        return "LOW"
    if ratio < 0.5:
        return "MODERATE"
    if ratio < 0.8:
        return "HIGH"
    return "BLOCKING"


def _variance(values: list[float]) -> float:
    return round(pvariance(values), 6) if len(values) > 1 else 0.0


def _entry(
    context: PlanningContext,
    plan: CandidatePlan,
    rollout: PlanRollout,
    index: int,
    settings: ComfortLedgerSettings,
    consecutive: int,
) -> ComfortLedgerEntry:
    point = rollout.points[index]
    values = (
        point.predicted_temperature_c,
        point.lower_temperature_c,
        point.upper_temperature_c,
        point.expected_occupancy,
    )
    if not all(math.isfinite(value) for value in values):
        raise LedgerValidationError("non_finite_ledger_input")
    occupied = point.expected_occupancy > 0
    point_time = datetime.strptime(context.planning_timestamp, "%m-%d %H:%M") + timedelta(
        minutes=context.timestep_minutes * point.timestep
    )
    protected = occupied and any(
        event.comfort_protection
        and datetime.strptime(event.start_timestamp, "%m-%d %H:%M")
        <= point_time
        <= datetime.strptime(event.end_timestamp, "%m-%d %H:%M")
        for event in context.events
    )
    lower = (
        settings.protected_event_lower_c
        if protected
        else (settings.occupied_lower_c if occupied else settings.unoccupied_lower_c)
    )
    upper = (
        settings.protected_event_upper_c
        if protected
        else (settings.occupied_upper_c if occupied else settings.unoccupied_upper_c)
    )
    duration = context.timestep_minutes / 60.0
    weight = 1.25 if protected else 1.0
    occupancy_weight = 1.0 if occupied else 0.0
    central_exceedance = max(0.0, point.predicted_temperature_c - upper)
    central_exceedance += max(0.0, lower - point.predicted_temperature_c)
    uncertainty_exceedance = max(0.0, point.upper_temperature_c - upper)
    uncertainty_exceedance += max(0.0, lower - point.lower_temperature_c)
    central = occupancy_weight * duration * weight * central_exceedance
    uncertainty = occupancy_weight * duration * weight * uncertainty_exceedance
    burden = max(central, uncertainty)
    margin = max(
        0.0, min(point.predicted_temperature_c - lower, upper - point.predicted_temperature_c)
    )
    credit = (
        0.0
        if central or not occupied
        else min(
            settings.maximum_credit_per_timestep,
            duration * margin * (0.5 if uncertainty else 1.0),
        )
    )
    reasons = []
    if not occupied:
        reasons.append("unoccupied_no_comfort_burden")
    elif burden:
        reasons.append("protected_event_burden" if protected else "occupied_boundary_burden")
    else:
        reasons.append("within_occupied_boundary")
    payload = {
        "context": context.context_id,
        "plan": plan.plan_id,
        "rollout": rollout.rollout_id,
        "timestep": point.timestep,
    }
    return ComfortLedgerEntry(
        entry_id=planning_fingerprint(payload),
        account_id=planning_fingerprint({"zone": context.target_zone, "ledger": 1}),
        context_id=context.context_id,
        plan_id=plan.plan_id,
        rollout_id=rollout.rollout_id,
        event_id=context.events[0].event_type if protected else None,
        timestep=point.timestep,
        simulation_timestamp=point_time.strftime("%m-%d %H:%M"),
        entry_type="BURDEN" if burden else "CREDIT",
        evidence_type="PREDICTED_LEDGER_ENTRY",
        occupancy=point.expected_occupancy,
        occupied=occupied,
        protected_event=protected,
        lower_boundary_c=lower,
        upper_boundary_c=upper,
        predicted_temperature_c=point.predicted_temperature_c,
        lower_uncertainty_c=point.lower_temperature_c,
        upper_uncertainty_c=point.upper_temperature_c,
        central_burden=round(central, 6),
        uncertainty_burden=round(uncertainty, 6),
        total_burden=round(burden, 6),
        credit=round(credit, 6),
        debt=round(burden, 6),
        repayment=0.0,
        consecutive_burden_count=consecutive,
        reason_codes=tuple(reasons),
        provenance={"model_id": rollout.model_id, "formula": settings.burden_method},
    )


def evaluate_rollout(
    context: PlanningContext,
    plan: CandidatePlan,
    rollout: PlanRollout,
    ledger: ComfortLedgerSettings,
    bank: ThermalBankSettings,
    *,
    opening_credit: float = 0.0,
    opening_debt: float = 0.0,
    opening_bank_balance: float = 0.0,
) -> LedgerPlanEvaluation:
    if plan.plan_id != rollout.plan_id or plan.context_id != rollout.context_id:
        raise LedgerValidationError("plan_rollout_context_mismatch")
    if plan.target_zone != ledger.target_zone or plan.target_zone != bank.target_zone:
        raise LedgerValidationError("wrong_ledger_zone")
    if min(opening_credit, opening_debt, opening_bank_balance) < 0:
        raise LedgerValidationError("negative_opening_balance")
    entries = []
    consecutive = 0
    for index, point in enumerate(rollout.points):
        occupied = point.expected_occupancy > 0
        upper = ledger.occupied_upper_c
        lower = ledger.occupied_lower_c
        has_risk = occupied and (
            point.upper_temperature_c > upper or point.lower_temperature_c < lower
        )
        consecutive = consecutive + 1 if has_risk else 0
        entries.append(_entry(context, plan, rollout, index, ledger, consecutive))
    burden = round(sum(item.total_burden for item in entries), 6)
    credit = round(min(ledger.maximum_credit_per_horizon, sum(item.credit for item in entries)), 6)
    repayment = round(min(opening_debt, credit * ledger.repayment_fraction), 6)
    debt = round(min(ledger.maximum_debt, max(0.0, opening_debt + burden - repayment)), 6)
    status = _debt_status(debt, ledger.maximum_debt)
    maximum_consecutive = max((item.consecutive_burden_count for item in entries), default=0)
    protected_burden = round(sum(item.total_burden for item in entries if item.protected_event), 6)
    chunks = [entries[index :: ledger.fairness_windows] for index in range(ledger.fairness_windows)]
    window_burden = [sum(item.total_burden for item in chunk) for chunk in chunks]
    concentration = max(window_burden, default=0.0) / burden if burden else 0.0
    recovery_ratio = (
        min(1.0, repayment / opening_debt) if opening_debt else (1.0 if burden == 0 else 0.0)
    )
    debt_credit = debt / credit if credit else (debt if debt else 0.0)
    fairness_reasons = []
    if concentration > 0.75:
        fairness_reasons.append("temporal_burden_concentration")
    if maximum_consecutive > ledger.consecutive_burden_limit:
        fairness_reasons.append("consecutive_burden_limit_exceeded")
    if protected_burden:
        fairness_reasons.append("protected_event_burden")
    fairness = ComfortFairnessAssessment(
        assessment_id=planning_fingerprint({"fairness": rollout.rollout_id}),
        context_id=context.context_id,
        plan_id=plan.plan_id,
        maximum_event_burden=protected_burden,
        burden_concentration_ratio=round(concentration, 6),
        maximum_consecutive_burden=maximum_consecutive,
        recovery_coverage_ratio=round(recovery_ratio, 6),
        debt_to_credit_ratio=round(debt_credit, 6),
        protected_event_burden_count=sum(
            item.protected_event and item.total_burden > 0 for item in entries
        ),
        repeated_burden_selection_count=max(0, maximum_consecutive - 1),
        temporal_burden_variance=_variance(window_burden),
        event_burden_variance=0.0,
        maximum_debt_age=0,
        status="PASS" if not fairness_reasons else "WARNING",
        reason_codes=tuple(fairness_reasons),
    )
    penalties = {
        "burden": min(1.0, burden / ledger.maximum_horizon_burden),
        "concentration": concentration,
        "consecutive": min(1.0, maximum_consecutive / ledger.consecutive_burden_limit),
        "recovery": 1.0 - recovery_ratio,
        "debt": min(1.0, debt / ledger.maximum_debt),
        "protected_event": min(1.0, protected_burden / ledger.maximum_horizon_burden),
    }
    equity = round(
        100.0 * (1.0 - sum(ledger.equity_weights[k] * v for k, v in penalties.items())), 6
    )
    blocking = []
    if status == "BLOCKING" and burden > 0:
        blocking.append("blocking_comfort_debt")
    if protected_burden > ledger.maximum_horizon_burden:
        blocking.append("protected_event_burden_limit_exceeded")
    if rollout.qualification_status == "NOT_QUALIFIED_FOR_RANKING":
        blocking.append("strong_ood_rejected")
    deposit = 0.0
    if plan.strategy_type == "PRECONDITION_BEFORE_PEAK" and not blocking:
        deposit = min(bank.maximum_deposit_per_horizon, credit * bank.credit_to_bank_conversion)
    available_before_reserves = opening_bank_balance + deposit
    uncertainty_reserve = round(
        min(available_before_reserves, deposit * bank.uncertainty_reserve_fraction), 6
    )
    remaining = max(0.0, available_before_reserves - uncertainty_reserve)
    protected_reserve = round(
        min(remaining, bank.protected_event_reserve if context.events else 0.0), 6
    )
    available = max(0.0, remaining - protected_reserve)
    withdrawal = 0.0
    if plan.strategy_type in {"VACANCY_RELAXATION", "BALANCED"} and not blocking:
        withdrawal = min(available, bank.withdrawal_limit_per_event)
    debt_penalty = min(max(0.0, available - withdrawal), debt * bank.debt_to_bank_penalty)
    closing = closing_balance(
        opening=opening_bank_balance,
        deposit=deposit,
        withdrawal=withdrawal,
        decay=0.0,
        expiry=0.0,
        debt_penalty=debt_penalty,
        uncertainty_reserve=uncertainty_reserve,
        protected_event_reserve=protected_reserve,
        settings=bank,
    )
    bank_summary = ThermalBankSummary(
        opening_balance=opening_bank_balance,
        deposit=round(deposit, 6),
        withdrawal=round(withdrawal, 6),
        decay=0.0,
        expiry=0.0,
        debt_penalty=round(debt_penalty, 6),
        uncertainty_reserve=uncertainty_reserve,
        protected_event_reserve=protected_reserve,
        available_balance=round(available, 6),
        closing_balance=closing,
        reason_codes=("relative_advisory_units", "no_physical_energy_claim"),
    )
    ledger_score = round(
        rollout.microtwin_score
        + burden
        + debt * 0.5
        + maximum_consecutive * 0.25
        + protected_burden
        - equity * 0.02
        - deposit * 0.1
        + withdrawal * 0.1,
        6,
    )
    evaluation_id = planning_fingerprint(
        {
            "rollout": rollout.rollout_id,
            "opening_debt": opening_debt,
            "opening_bank": opening_bank_balance,
        }
    )
    return LedgerPlanEvaluation(
        evaluation_id=evaluation_id,
        plan_id=plan.plan_id,
        rollout_id=rollout.rollout_id,
        context_id=context.context_id,
        strategy_type=plan.strategy_type,
        entries=tuple(entries),
        opening_comfort_credit=opening_credit,
        opening_comfort_debt=opening_debt,
        new_comfort_burden=burden,
        comfort_credit=credit,
        debt_repayment=repayment,
        closing_comfort_debt=debt,
        debt_status=status,
        recovery_obligation=round(max(0.0, debt * ledger.minimum_recovery), 6),
        maximum_consecutive_burden=maximum_consecutive,
        protected_event_burden=protected_burden,
        fairness=fairness,
        comfort_equity_score=max(0.0, min(100.0, equity)),
        bank=bank_summary,
        blocking_conditions=tuple(blocking),
        uncertainty="EMPIRICAL_BOUNDS; 12-step MAE 0.892340 C",
        ood_status=rollout.qualification_status,
        advisory_score=rollout.advisory_score,
        microtwin_score=rollout.microtwin_score,
        ledger_aware_score=ledger_score,
        eligible=plan.eligible and not blocking,
        rejection_reasons=tuple(blocking),
    )


def evaluate_candidates(
    context: PlanningContext,
    plans: tuple[CandidatePlan, ...],
    rollouts: tuple[PlanRollout, ...],
    ledger: ComfortLedgerSettings,
    bank: ThermalBankSettings,
) -> tuple[LedgerPlanEvaluation, ...]:
    by_plan = {plan.plan_id: plan for plan in plans}
    return tuple(
        evaluate_rollout(context, by_plan[item.plan_id], item, ledger, bank) for item in rollouts
    )


def rank_evaluations(
    context: PlanningContext,
    plans: tuple[CandidatePlan, ...],
    rollouts: tuple[PlanRollout, ...],
    evaluations: tuple[LedgerPlanEvaluation, ...],
) -> LedgerRanking:
    eligible = sorted(
        (item for item in evaluations if item.eligible),
        key=lambda item: (item.ledger_aware_score, item.plan_id),
    )
    if not eligible:
        raise LedgerValidationError("no_ledger_eligible_plan")
    module11 = tuple(
        plan.plan_id
        for plan in sorted(
            (plan for plan in plans if plan.eligible),
            key=lambda item: (item.advisory_score, item.plan_id),
        )
    )
    module12 = tuple(item.plan_id for item in rank_rollouts(rollouts))
    module13 = tuple(item.plan_id for item in eligible)
    return LedgerRanking(
        ranking_id=planning_fingerprint({"context": context.context_id, "ranking": module13}),
        context_id=context.context_id,
        module11_ranking=module11,
        module12_ranking=module12,
        module13_ranking=module13,
        rankings_all_agree=module11 == module12 == module13,
        selected_plan_id=module13[0],
    )
