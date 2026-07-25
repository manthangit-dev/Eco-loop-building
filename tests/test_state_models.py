from dataclasses import FrozenInstanceError, replace

import pytest
from src.state.models import (
    DuplicateZoneError,
    InvalidTimestampError,
    NonFiniteValueError,
    UnsupportedSchemaVersionError,
)

from tests.state_helpers import sample_state


def test_building_state_is_immutable_and_serializable() -> None:
    state = sample_state()
    with pytest.raises(FrozenInstanceError):
        state.sequence = 2  # type: ignore[misc]
    assert '"schema_version":1' in state.to_json()


def test_state_rejects_schema_duplicates_and_non_finite_values() -> None:
    state = sample_state()
    with pytest.raises(UnsupportedSchemaVersionError):
        replace(state, schema_version=2)
    with pytest.raises(DuplicateZoneError):
        replace(state, zones=(state.zones[0], state.zones[0]))
    with pytest.raises(NonFiniteValueError):
        replace(state, outdoor=replace(state.outdoor, dry_bulb_c=float("nan")))


def test_clock_rejects_invalid_timestamp() -> None:
    with pytest.raises(InvalidTimestampError):
        replace(sample_state().clock, month=13)
    with pytest.raises(InvalidTimestampError):
        replace(sample_state().clock, minute=100)
