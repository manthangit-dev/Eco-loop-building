from src.agent.scenarios import SCENARIOS


def test_exactly_fifty_named_scenarios() -> None:
    assert len(SCENARIOS) == len(set(SCENARIOS)) == 50
