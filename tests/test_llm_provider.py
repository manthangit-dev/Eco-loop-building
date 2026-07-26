import pytest
from src.llm.mock_provider import DeterministicMockProvider
from src.llm.models import ProviderMessage, ProviderOutput


def test_mock_is_scripted_bounded_and_cancellable() -> None:
    expected = ProviderOutput(text="bounded")
    provider = DeterministicMockProvider([expected])
    assert (
        provider.health_check()
        and provider.generate([ProviderMessage(role="user", content="x")]) == expected
    )
    assert provider.count_or_estimate_tokens("12345") == 2
    provider.cancel()
    with pytest.raises(RuntimeError, match="cancelled"):
        provider.generate([])
    provider.close()


def test_empty_mock_response_fails() -> None:
    with pytest.raises(RuntimeError, match="empty"):
        DeterministicMockProvider([]).generate([])
