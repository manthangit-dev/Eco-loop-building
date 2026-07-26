# Deterministic Fallback Controller

## Purpose and boundary

Module 7 provides an LLM-independent, state-driven cooling-setpoint fallback. It consumes
immutable Module 6 `BuildingState` records and produces typed decisions for the next
control period. It is reliable fallback behavior, not optimization.

```text
Canonical BuildingState
        |
Deterministic fallback decision engine
        |
ControlDecision
        |
Bounded latest-command buffer
        |
Single approved cooling actuator executor
        |
EnergyPlus
        |
Subsequent BuildingState observation
```

The independent Module 8 safety guard is pending. Every decision records
`not_implemented_module_8_pending`; Module 7 actions are not an interface for future LLM
proposals.

## State, timing, and policy

Decisions use only a completed canonical state. `based_on_state_sequence=N` produces a
command with `valid_from_sequence=N+1`, preventing same-state or future-state use. The
controller evaluates once per 15-minute zone timestep in deterministic zone-ID order.

Per-zone immutable memory tracks native/previous mode, occupancy counters, hold countdown,
recovery/hysteresis, last native and commanded setpoint, command expiry, reset sequence,
and reason. Modes are `NATIVE`, `OCCUPIED_NORMAL`, `OCCUPIED_RECOVERY`, `VACANCY_GRACE`,
`UNOCCUPIED_RELAXED`, `HOLD`, `FAILSAFE_RESET`, and `DISABLED`.

- Occupied zones retain the latest verified effective setpoint. Above 25.0°C, recovery
  requests no more than the 23.9°C configured recovery value.
- A 0.5°C hysteresis band prevents immediate recovery exit.
- Every transition has a four-zone-timestep minimum hold.
- Recently vacant zones retain normal behavior for four timesteps.
- Later vacancy permits a +1.0°C relaxation, capped at 30.0°C and no more than 1.0°C from
  the retained native baseline. Relaxation is prevented at or above 27.0°C.
- Commands expire after two sequences. Replacement is explicit and bounded. Missing or
  invalid baseline/temperature data fails closed to reset/native control.
- `PLENUM-1` and unapproved zones are never controlled.

The command buffer retains only the latest immutable command, rejects duplicates,
decreasing sequences, expiry, and any actuator other than the configured one. Shutdown
clears the buffer. The executor performs no policy evaluation, database access, file I/O,
network call, or LLM call inside its EnergyPlus callback.

## Actuation and persistence

Live control uses only:

`Zone Temperature Control / Cooling Setpoint / SPACE3-1 / C`

This is the Module 5 verified isolated occupied-zone actuator. The executor uses
`callback_after_predictor_before_hvac_managers`, skips readiness/warmup/non-weather calls,
reapplies the latest valid command, and resets on shutdown.

Schema migration 1→2 preserves Module 6 tables and adds structured controller runs,
decisions, commands, events, outcomes, and memory-snapshot tables with indexes and foreign
keys. A bounded writer batches 100 decisions. Real commands link to later state observations;
these are labeled post-command associations, not causal effects.

## Commands

```powershell
python scripts/replay_fallback_controller.py --output-directory data/output/module_7_fallback_controller/replay_shadow/run_1
python scripts/run_fallback_shadow.py
python scripts/run_fallback_controller.py
python scripts/validate_fallback_controller.py --mode live_control
python scripts/inspect_controller_decisions.py --database data/output/module_7_fallback_controller/live_control/current/thermoledger_state.db --query recent
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/verify_fallback_controller.ps1
```

Inspection offers predefined read-only queries only.

## Verified annual results — 2026-07-25

Two replay-shadow executions each streamed 35,040 states, produced 175,200 fail-closed
decisions/commands, zero plenum actions, and zero writes. Module 6 replay lacks the optional
effective setpoint, so all replay decisions correctly used `REJECT_MISSING_DATA` /
`FAILSAFE_RESET`. Canonical fingerprint `c4e6f16b…0954b` matched across both runs.

Live shadow persisted 35,040 states, 175,200 decisions/commands, and zero actuator writes.
It passed physical parity with Module 6. Its decisions included 140,160 holds, 11,707
occupied-normal, 7 occupied-recovery, 22,276 unoccupied-relaxed, and 1,050 vacancy-grace.

Live control persisted 35,040 states, decisions, and commands plus 35,039 subsequent-state
outcomes. It used one actuator, made 51,538 system-timestep set calls, 35,039 explicit command
replacements, and one shutdown reset. Setpoint observations ranged 28.4–30.0°C. Modes were:

- `HOLD`: 28,032
- `OCCUPIED_NORMAL`: 1,468
- `OCCUPIED_RECOVERY`: 831
- `UNOCCUPIED_RELAXED`: 4,499
- `VACANCY_GRACE`: 210

Compared with Module 6, annual average diagnostic differences were +0.2795°C target-zone
temperature, −32,723 J/timestep facility electricity, and −4,117 J/timestep HVAC electricity.
These are experimental associations, not savings, optimization results, or comfort claims.

EnergyPlus exited zero with zero warnings, severe/fatal errors, API errors, callback errors,
subscriber errors, or persistence errors. SQLite integrity was `ok` with zero foreign-key
violations. The full verifier passed 145 tests, Ruff, strict Mypy, both replays, live shadow,
live control, validators, comparison, and forbidden-feature scanning.

## Limitations

The real controller is limited to one actuator and one example building. The effective
setpoint field is absent in Module 6 replay, so replay demonstrates deterministic fail-closed
behavior rather than hypothetical setpoint changes. System-timestep reapplication produces
more set calls than zone decisions. Databases are large (about 560 MB live control, 702 MB
live shadow, and 211 MB per replay). No final safety guard, LLM, MCP, comfort debt,
flexibility scoring, tariff/carbon logic, or optimization exists. There is no verified
energy-saving result.
