# ThermoLedger AI

Module 14A now rejects the original January/July mismatch and records three exact July 19
short runs. The live result had a meaningful measured effect, one guarded set, one guarded
reset, and zero unguarded writes. See `docs/CONTEXT_ALIGNED_EXECUTION.md`.

Module 15 provides the final local-only, read-only evidence dashboard and deterministic
hackathon package. It has no planning, approval, execution, EnergyPlus, or Ollama path. See
`docs/EVIDENCE_DASHBOARD.md` and `docs/HACKATHON_DEMO_SCRIPT.md`.

Module 12 adds a qualified offline MicroTwin for deterministic, advisory-only candidate-plan rollouts. It is not an EnergyPlus result and does not claim verified savings or comfort improvement. See [docs/MICROTWIN.md](docs/MICROTWIN.md).

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
| 7 | Rule-based fallback controller | Completed |
| 8 | Safety guard | Completed |
| 9 | Local MCP server and deterministic building tool layer | Completed |
| 10 | Local LLM adapter and controlled MCP supervisor | Completed |
| 11 | Forecast context and deterministic advisory planning | Completed |
| 12 | Offline MicroTwin candidate evaluation | Completed |
| 13 | Comfort Ledger and Thermal Bank | Completed |
| 14 | Approval-gated simulation execution | Completed |
| 15 | Read-only evidence dashboard and hackathon package | Completed |
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

Module 9 provides 18 deterministic local stdio tools over recorded Modules 6–8 evidence.
The control-capable tool is disabled. See [docs/MCP_SERVER.md](docs/MCP_SERVER.md).

Module 10 adds a bounded advisory supervisor, deterministic mock, loopback-only Ollama
adapter, strict tool policy, and schema-v5 audit. Official Ollama with `qwen3:0.6b`
completed native tool calling and recorded-data real-model smoke with zero writes.
See [docs/LLM_SUPERVISOR.md](docs/LLM_SUPERVISOR.md).

Module 11 adds versioned local forecast scenarios, deterministic advisory candidate
plans, transparent scoring, six MCP planning tools, and bounded local-model plan
selection. It performs no physical execution and makes no savings prediction. See
[docs/PLANNING_ENGINE.md](docs/PLANNING_ENGINE.md).

For a tested recorded-data demonstration with no Ollama, EnergyPlus process, or physical
write, run `powershell.exe -NoProfile -ExecutionPolicy Bypass -File
scripts\run_current_demo.ps1`. See [docs/CURRENT_DEMO.md](docs/CURRENT_DEMO.md).

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

Through Module 6 the repository had no controller; Module 7 below adds only the deterministic
fallback. Comfort debt, AI, MCP, the dashboard, and energy-saving results remain absent.

## Deterministic fallback controller — Module 7

Module 7 consumes canonical states and produces causal, bounded cooling-setpoint commands
without an LLM or external service. Replay and live shadow evaluate all five occupied zones;
real control is restricted to the verified `SPACE3-1` cooling-setpoint actuator.

```powershell
python scripts/replay_fallback_controller.py --output-directory data/output/module_7_fallback_controller/replay_shadow/run_1
python scripts/run_fallback_shadow.py
python scripts/run_fallback_controller.py
python scripts/validate_fallback_controller.py --mode live_control
python scripts/inspect_controller_decisions.py --database data/output/module_7_fallback_controller/live_control/current/thermoledger_state.db --query recent
```

Two annual replays were deterministic; annual live shadow preserved Module 6 physical parity
with zero writes; annual live control persisted 35,040 states and decisions, used one
actuator, observed setpoint response, and reset on shutdown. See
[docs/FALLBACK_CONTROLLER.md](docs/FALLBACK_CONTROLLER.md).

Module 7's historical records correctly state that the guard was pending during its run.
Module 8 below now protects the physical path. No LLM, MCP, comfort debt, optimization, or
validated energy-saving result exists.

## Independent safety guard — Module 8

Module 8 now places an independent, deterministic, fail-closed gate between every proposal
and the physical writer. Only an immutable runtime-validated `GuardedCommand` for the exact
`SPACE3-1` cooling-setpoint actuator can be written; raw commands, forged commands, plenums,
wrong identities, non-finite values, stale/future commands, and audit failures fail closed.

```powershell
.\.venv\Scripts\python.exe scripts/run_safety_challenges.py --output data/output/module_8_safety_guard/challenges/run_1/safety_challenge_report.json
.\.venv\Scripts\python.exe scripts/replay_safety_guard.py --output data/output/module_8_safety_guard/replay/run_1/safety_replay_report.json
.\.venv\Scripts\python.exe scripts/run_safety_shadow.py
.\.venv\Scripts\python.exe scripts/run_guarded_controller.py
.\.venv\Scripts\python.exe scripts/validate_safety_guard.py
.\.venv\Scripts\python.exe scripts/inspect_safety_guard.py --query summary
```

The challenge suite, repeated replay, annual shadow, and annual guarded-control run pass.
All 51,539 physical set/reset attempts are traceable to guard decisions. See
[docs/SAFETY_GUARD.md](docs/SAFETY_GUARD.md). Module 9 is next and remains pending. No LLM,
MCP, optimization, or validated saving result exists.

## Results — not yet generated

No results have been generated. The 10% energy and peak-demand reductions, 95% occupied comfort compliance, and 98% successful control cycles are targets, not achievements.

Achieved savings may be claimed only after real baseline and controlled simulations use the identical building, weather, occupancy, external signals, and time periods, and their outputs are compared.
# Module 13: Comfort Ledger and Thermal Bank

Status: **Completed and fully verified.**

Module 13 adds an advisory-only, equity-aware decision layer over the five qualified Module 12 MicroTwin rollouts. It deterministically records comfort burden and debt, evaluates fairness, maintains a zero-overdraft Thermal Bank in RTFU, and compares Module 11, Module 12, and ledger-aware rankings. It performs no physical control, EnergyPlus execution, model retraining, or verified-savings measurement. See [Comfort Ledger](docs/COMFORT_LEDGER.md), [Thermal Bank](docs/THERMAL_BANK.md), and [Module 13 design decision](docs/MODULE_13_DESIGN_DECISION.md).

# Module 14: Approval-Gated Simulation Execution

Status: **Completed and fully verified.** Module 14 binds the persisted ledger-selected plan to an immutable local operator approval, schedules it against committed EnergyPlus state, revalidates every action through Module 8, and uses the existing physical writer. The bounded live test made one guarded set and one guarded reset; no annual or real-building claim is made. See [Execution Orchestrator](docs/EXECUTION_ORCHESTRATOR.md), [Operator Approval](docs/OPERATOR_APPROVAL.md), and [Short-Horizon Validation](docs/SHORT_HORIZON_VALIDATION.md).
