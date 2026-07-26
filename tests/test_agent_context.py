import pytest
from src.agent.context_manager import enforce_budget, estimate_tokens, summarise_tool_result
from src.llm.models import ProviderMessage


def test_summary_and_token_budget_are_deterministic() -> None:
    assert estimate_tokens("12345") == 2
    assert summarise_tool_result([{"x": 1}] * 100, 40).startswith('{"count":100')
    messages = (
        ProviderMessage(role="system", content="safe"),
        ProviderMessage(role="tool", content="x" * 1000),
        ProviderMessage(role="user", content="objective"),
    )
    bounded = enforce_budget(messages, 20)
    assert [item.role for item in bounded] == ["system", "user"]
    with pytest.raises(ValueError, match="context_budget"):
        enforce_budget((ProviderMessage(role="system", content="x" * 1000),), 1)
