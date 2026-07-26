from src.mcp_server.models import ToolClassification
from src.mcp_server.registry import build_registry, catalogue_fingerprint


def test_registry_order_classification_and_fingerprint() -> None:
    first, second = build_registry(False), build_registry(False)
    assert len(first) == 44 and first == second
    assert catalogue_fingerprint(first) == catalogue_fingerprint(second)
    assert sum(item.classification == ToolClassification.READ_ONLY for item in first) == 34
    assert sum(item.classification == ToolClassification.PROPOSAL_ONLY for item in first) == 9
    control = [item for item in first if item.classification == ToolClassification.CONTROL_CAPABLE]
    assert len(control) == 1 and not control[0].enabled
    names = {item.name for item in first}
    assert {
        "get_microtwin_status",
        "get_microtwin_validation",
        "evaluate_plan_with_microtwin",
        "compare_microtwin_rollouts",
        "get_microtwin_rollout",
        "rank_plans_with_microtwin",
    } <= names
    assert "train_microtwin" not in names
    assert catalogue_fingerprint(first) == (
        "b97af3b310e48b0014f9a00a34e83737d6798b7fcda58da957b98a985477dcd6"
    )
