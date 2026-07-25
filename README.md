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
| 2 | Baseline EnergyPlus building | Pending |
| 3 | Python EnergyPlus runner | Pending |
| 4 | Live sensor extraction | Pending |
| 5 | Actuator injection | Pending |
| 6 | State bus and storage | Pending |
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

## Results — not yet generated

No results have been generated. The 10% energy and peak-demand reductions, 95% occupied comfort compliance, and 98% successful control cycles are targets, not achievements.

Achieved savings may be claimed only after real baseline and controlled simulations use the identical building, weather, occupancy, external signals, and time periods, and their outputs are compared.
