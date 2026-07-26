from __future__ import annotations

import pytest

from tests.fixtures.microtwin.negative_fixtures import FACTORIES


@pytest.mark.parametrize("fixture_name", sorted(FACTORIES))
def test_dedicated_negative_fixture(fixture_name: str) -> None:
    result = FACTORIES[fixture_name]()
    assert result.status == "PASS", (fixture_name, result.reason_code)
    assert result.assertions >= 2
    assert result.persistence_delta == 0
    assert result.physical_write_delta == 0
    assert result.energyplus_process_delta == 0
