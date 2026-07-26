"""Canonical deterministic Module 9 tool registry."""

from src.mcp_server.models import ToolClassification, ToolDefinition, fingerprint

TOOL_SPECS: tuple[tuple[str, str, ToolClassification], ...] = (
    ("list_available_runs", "List bounded persisted runs.", ToolClassification.READ_ONLY),
    ("get_run_metadata", "Read metadata for one run.", ToolClassification.READ_ONLY),
    ("get_building_state", "Read one committed building state.", ToolClassification.READ_ONLY),
    ("get_zone_state", "Read one exact zone state.", ToolClassification.READ_ONLY),
    ("get_recent_state_history", "Read bounded state history.", ToolClassification.READ_ONLY),
    (
        "get_controller_status",
        "Inspect deterministic controller status.",
        ToolClassification.READ_ONLY,
    ),
    (
        "get_controller_decisions",
        "Read bounded controller decisions.",
        ToolClassification.READ_ONLY,
    ),
    ("get_safety_guard_status", "Inspect safety configuration.", ToolClassification.READ_ONLY),
    ("get_safety_decisions", "Read bounded guard decisions.", ToolClassification.READ_ONLY),
    (
        "get_physical_write_audit",
        "Read bounded physical-write audit.",
        ToolClassification.READ_ONLY,
    ),
    (
        "inspect_energyplus_errors",
        "Read bounded EnergyPlus diagnostics.",
        ToolClassification.READ_ONLY,
    ),
    (
        "get_energyplus_execution_status",
        "Read recorded execution status.",
        ToolClassification.READ_ONLY,
    ),
    (
        "list_available_actuators",
        "List persisted verified actuators.",
        ToolClassification.READ_ONLY,
    ),
    (
        "get_run_energy_summary",
        "Summarize recorded energy diagnostics.",
        ToolClassification.READ_ONLY,
    ),
    ("compare_runs", "Compare compatible recorded runs.", ToolClassification.READ_ONLY),
    (
        "get_comfort_evidence",
        "Return available comfort evidence only.",
        ToolClassification.READ_ONLY,
    ),
    (
        "validate_control_proposal",
        "Dry-run proposal through Module 8.",
        ToolClassification.PROPOSAL_ONLY,
    ),
    (
        "get_forecast_context",
        "Return bounded local planning forecast context.",
        ToolClassification.READ_ONLY,
    ),
    (
        "generate_candidate_plans",
        "Generate deterministic advisory candidates.",
        ToolClassification.PROPOSAL_ONLY,
    ),
    (
        "evaluate_candidate_plan",
        "Inspect one persisted candidate plan.",
        ToolClassification.READ_ONLY,
    ),
    (
        "compare_candidate_plans",
        "Compare persisted eligible candidates.",
        ToolClassification.READ_ONLY,
    ),
    ("get_planning_session", "Read a persisted planning session.", ToolClassification.READ_ONLY),
    (
        "select_advisory_plan",
        "Persist an advisory-only candidate selection.",
        ToolClassification.PROPOSAL_ONLY,
    ),
    (
        "get_microtwin_status",
        "Read qualified offline MicroTwin status.",
        ToolClassification.READ_ONLY,
    ),
    (
        "get_microtwin_validation",
        "Read held-out MicroTwin validation.",
        ToolClassification.READ_ONLY,
    ),
    (
        "evaluate_plan_with_microtwin",
        "Evaluate one existing plan counterfactually.",
        ToolClassification.PROPOSAL_ONLY,
    ),
    (
        "compare_microtwin_rollouts",
        "Compare persisted MicroTwin rollouts.",
        ToolClassification.READ_ONLY,
    ),
    ("get_microtwin_rollout", "Read one bounded MicroTwin rollout.", ToolClassification.READ_ONLY),
    (
        "rank_plans_with_microtwin",
        "Rank eligible plans using qualified MicroTwin evidence.",
        ToolClassification.PROPOSAL_ONLY,
    ),
    ("get_comfort_ledger_status", "Read Comfort Ledger status.", ToolClassification.READ_ONLY),
    ("get_comfort_ledger_entries", "Read bounded ledger entries.", ToolClassification.READ_ONLY),
    (
        "evaluate_plan_comfort_ledger",
        "Evaluate persisted rollout burden.",
        ToolClassification.PROPOSAL_ONLY,
    ),
    (
        "compare_comfort_ledger_evaluations",
        "Compare ledger evaluations.",
        ToolClassification.READ_ONLY,
    ),
    ("get_thermal_bank_status", "Read relative Thermal Bank status.", ToolClassification.READ_ONLY),
    (
        "get_thermal_bank_transactions",
        "Read bounded bank transactions.",
        ToolClassification.READ_ONLY,
    ),
    (
        "evaluate_plan_thermal_bank",
        "Evaluate advisory RTFU accounting.",
        ToolClassification.PROPOSAL_ONLY,
    ),
    (
        "rank_plans_with_ledger",
        "Rank persisted plans with ledger evidence.",
        ToolClassification.PROPOSAL_ONLY,
    ),
    ("get_ledger_ranking", "Read all three advisory rankings.", ToolClassification.READ_ONLY),
    (
        "select_ledger_advisory_plan",
        "Persist ledger advisory selection.",
        ToolClassification.PROPOSAL_ONLY,
    ),
    (
        "get_execution_approval_status",
        "Read execution approval status.",
        ToolClassification.READ_ONLY,
    ),
    ("get_plan_execution_status", "Read plan execution status.", ToolClassification.READ_ONLY),
    ("get_plan_execution_audit", "Read bounded execution audit.", ToolClassification.READ_ONLY),
    (
        "compare_execution_runs",
        "Compare compatible short execution runs.",
        ToolClassification.READ_ONLY,
    ),
    (
        "propose_guarded_control",
        "Request guarded live control.",
        ToolClassification.CONTROL_CAPABLE,
    ),
)


def build_registry(control_enabled: bool) -> tuple[ToolDefinition, ...]:
    return tuple(
        ToolDefinition(
            name=name,
            purpose=purpose,
            classification=classification,
            enabled=classification != ToolClassification.CONTROL_CAPABLE or control_enabled,
        )
        for name, purpose, classification in TOOL_SPECS
    )


def catalogue_fingerprint(registry: tuple[ToolDefinition, ...]) -> str:
    return fingerprint([item.model_dump(mode="json") for item in registry])
