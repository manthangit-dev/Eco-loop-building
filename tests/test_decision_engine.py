import pytest
from src.control.decision_engine import FallbackDecisionEngine
from src.state.models import NonMonotonicSequenceError

from tests.control_helpers import control_state, settings


def test_engine_is_causal_ordered_and_shadow_evaluates_five_zones() -> None:
    engine = FallbackDecisionEngine("run", settings(), shadow=True)
    results = engine.evaluate(control_state())
    assert len(results) == 5
    assert [item[0].target_zone_id for item in results] == sorted(
        item[0].target_zone_id for item in results
    )
    assert all(item[0].intended_effective_sequence == 2 for item in results)
    with pytest.raises(NonMonotonicSequenceError):
        engine.evaluate(control_state())


def test_live_engine_targets_only_verified_zone() -> None:
    results = FallbackDecisionEngine("run", settings(), shadow=False).evaluate(control_state())
    assert len(results) == 1 and results[0][0].target_zone_name == "SPACE3-1"
