from src.control.decision_engine import FallbackDecisionEngine
from src.control.outcomes import observe_command

from tests.control_helpers import control_state, settings


def test_outcome_requires_subsequent_state() -> None:
    command = FallbackDecisionEngine("run", settings(), shadow=False).evaluate(control_state())[0][
        1
    ]
    assert command is not None
    assert observe_command(command, control_state()) is None
    assert observe_command(command, control_state(sequence=2)) is not None
