"""Identifiable focused tests for every Module 12C final-gap fixture."""

from __future__ import annotations

import pytest

from tests.fixtures.microtwin.negative_fixtures import FACTORIES

FINAL_GAPS = (
    "MT12-002",
    "MT12-003",
    "MT12-004",
    "MT12-005",
    "MT12-006",
    "MT12-009",
    "MT12-010",
    "MT12-011",
    "MT12-013",
    "MT12-014",
    "MT12-015",
    "MT12-016",
    "MT12-017",
    "MT12-018",
    "MT12-019",
    "MT12-027",
    "MT12-029",
    "MT12-050",
    "MT12-051",
    "MT12-062",
    "MT12-083",
    "MT12-089",
    "MT12-092",
    "MT12-096",
    "MT12-097",
)


@pytest.mark.parametrize("scenario_id", FINAL_GAPS, ids=FINAL_GAPS)
def test_module12c_dedicated_fixture(scenario_id: str) -> None:
    result = FACTORIES[scenario_id]()
    assert result.status == "PASS"
    assert result.reason_code
    assert result.production_entry_point.startswith("src.")
    assert result.mutation
    assert result.mutation_sensitive is True
    assert result.side_effect_checked is True
    assert result.persistence_delta == 0
    assert result.physical_write_delta == 0
    assert result.energyplus_process_delta == 0
