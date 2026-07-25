# ThermoLedger AI

> A Fair, Carbon-Aware Thermal Battery Agent for Autonomous Building Control

## Hackathon problem

Buildings need to lower electricity use and peak demand without repeatedly making the same occupied zone less comfortable. ThermoLedger AI will explore an autonomous, simulated controller that uses an EnergyPlus digital twin and a local LLM to plan safe thermal-battery actions.

## Proposed solution and innovations

The controller will pre-cool before costly or carbon-intensive periods, coast through peaks, then restore comfort. Its distinguishing mechanisms are a comfort-debt ledger that prevents repeated sacrifice of a zone, zone-flexibility scoring, and a candidate-action tournament across comfort-first, balanced, and energy-aggressive strategies.

## Closed-loop flow

EnergyPlus state → structured state bus → LLM/MCP planning tools → candidate evaluation → deterministic safety guard → EnergyPlus actuator injection → outcome observation → critic and self-correction.

The LLM proposes; deterministic code validates. Only validated actions may reach EnergyPlus, and a fallback controller must operate without the LLM.

## MVP scope

The frozen MVP uses EnergyPlus 26.1.0, Python 3.12, a five-zone office (`5ZoneAirCooled.idf`), 15-minute control intervals, cooling set-points as the primary control, ventilation multiplier as secondary control, local CSV tariff/carbon/occupancy signals, SQLite, CSV/JSON exports, Ollama, and Streamlit. Baseline and AI-controlled simulations will run separately with identical inputs.

No functional simulation, controller, dashboard, LLM, MCP, or application code exists yet. Module 0 established the repository foundation; Module 1 adds environment verification only.

## Technology decisions

| Area | Decision |
| --- | --- |
| Digital twin | EnergyPlus 26.1.0 |
| Language | Python 3.12 |
| LLM runtime | Ollama; exact model pending hardware inspection |
| Tool protocol | MCP-compatible Python tool server |
| Storage | SQLite; CSV and JSON analysis exports |
| Dashboard | Streamlit |

## Repository structure

`config/` contains frozen settings; `docs/` contains planning records; `models/`, `weather/`, and `data/` reserve simulation inputs and outputs; `src/` reserves future components; `dashboard/`, `scripts/`, `tests/`, and `results/` are intentionally empty placeholders.

## Development principles

Progress one module at a time. Preserve reproducibility, separate LLM planning from deterministic safety, retain an LLM-independent fallback, and never report targets as achieved without real comparable simulations.

## Module status

| Module | Name | Status |
| --- | --- | --- |
| 0 | Scope and repository foundation | Completed |
| 1 | Development environment | Completed |
| 2 | Baseline EnergyPlus building | Completed |
| 3 | Python EnergyPlus runner | Completed |
| 4 | Live sensor extraction | Completed |
| 5 | Actuator injection | Completed |
| 6 | State bus and storage | Completed |
| 7 | Rule-based fallback controller | Pending |
| 8 | Safety guard | Pending |
| 9 | Comfort-debt ledger | Pending |
| 10 | Zone-flexibility estimator | Pending |
| 11 | Thermal-battery strategy | Pending |
| 12 | Candidate-action tournament | Pending |
| 13 | Ollama and local LLM | Pending |
| 14 | MCP tool server | Pending |
| 15 | Agent orchestration | Pending |
| 16 | Critic and self-correction | Pending |
| 17 | Failure handling | Pending |
| 18 | Logging and observability | Pending |
| 19 | Baseline-versus-AI execution | Pending |
| 20 | Quantitative metrics | Pending |
| 21 | Streamlit dashboard | Pending |
| 22 | Automated testing | Pending |
| 23 | Experiment scenarios | Pending |
| 24 | Documentation | Pending |
| 25 | Presentation and demonstration | Pending |

## Setup — Module 1

Follow [docs/INSTALLATION.md](docs/INSTALLATION.md). Module 1 verification is read-only and does not run a building simulation.

## Baseline simulation — Module 2

Module 2 preserves the EnergyPlus 26.1 five-zone example and runs an uncontrolled Chicago
O'Hare TMY3 baseline using the EnergyPlus command line:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/run_baseline.ps1
python scripts/validate_baseline.py --config config/baseline.yaml
```

See [docs/BASELINE_MODEL.md](docs/BASELINE_MODEL.md) and
[docs/BASELINE_EXECUTION.md](docs/BASELINE_EXECUTION.md). No AI control or optimization exists
yet, and the baseline establishes no energy-saving claim.

## Python Runtime API — Module 3

Run and fully verify the unchanged baseline through the EnergyPlus Runtime API:

```powershell
python scripts/run_api_baseline.py --config config/api_runner.yaml
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/verify_api_runner.ps1
```

See [docs/PYTHON_API_RUNNER.md](docs/PYTHON_API_RUNNER.md).

## Live sensor extraction — Module 4

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/verify_sensor_extraction.ps1
```

See [docs/LIVE_SENSOR_EXTRACTION.md](docs/LIVE_SENSOR_EXTRACTION.md). The verified
annual run captured 35,040 read-only weather-period snapshots with zero callback or
API exchange errors and passed comparison with Module 3. No actuator control, AI,
optimization, or energy-saving claim exists.

## Safe runtime actuator injection — Module 5

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/verify_actuator_injection.ps1
```

See [docs/RUNTIME_ACTUATOR_INJECTION.md](docs/RUNTIME_ACTUATOR_INJECTION.md).
The deterministic one-zone test applied a bounded cooling-setpoint override,
observed its response, and released it with `reset_actuator`. No autonomous control,
AI, optimisation, or verified energy-saving claim exists.

## Canonical state bus and SQLite storage — Module 6

Module 6 normalizes immutable `BuildingState` records, publishes them through bounded
thread-safe history, and drains a bounded dedicated writer queue into schema-versioned
SQLite:

```powershell
python scripts/replay_sensor_states.py --state-config config/state_bus.yaml
python scripts/run_state_bus_integration.py --api-config config/api_runner.yaml --sensor-config config/sensors.yaml --state-config config/state_bus.yaml
python scripts/validate_state_storage.py --state-config config/state_bus.yaml --mode live
python scripts/inspect_state_database.py --state-config config/state_bus.yaml --mode live --recent 5 --zone-id space1_1
```

Both verified annual paths persisted 35,040 states and 210,240 zone rows, drained their
queues, and passed integrity and foreign-key checks. The live output passed comparison
with Module 4 and recorded zero actuator access. See
[docs/STATE_BUS_AND_STORAGE.md](docs/STATE_BUS_AND_STORAGE.md).

The repository has no autonomous controller, comfort-debt ledger, AI, or dashboard, and
no energy-saving result exists. Module 7, the deterministic fallback controller, is the
next pending module.

## Results — not yet generated

No results have been generated. The 10% energy and peak-demand reductions, 95% occupied comfort compliance, and 98% successful control cycles are targets, not achievements.

Achieved savings may be claimed only after real baseline and controlled simulations use the identical building, weather, occupancy, external signals, and time periods, and their outputs are compared.
