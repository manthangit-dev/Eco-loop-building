from __future__ import annotations

import pytest

from tests.fixtures.ledger.fixtures import FACTORIES


@pytest.mark.parametrize("scenario_id", sorted(FACTORIES), ids=sorted(FACTORIES))
def test_dedicated_ledger_replay_fixture(scenario_id: str) -> None:
    result = FACTORIES[scenario_id]()
    assert result.status == "PASS", (scenario_id, result.reason_code)
    assert result.assertions >= 3
    assert result.production_entry_point.startswith("src.")
    assert result.concrete_mutation
    assert result.actual_reason_checked
    assert result.persistence_checked
    assert result.mutation_sensitive
    assert result.physical_write_delta == 0
    assert result.energyplus_process_delta == 0
