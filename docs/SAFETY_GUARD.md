# Independent Safety Guard

## Purpose and trust boundary

Module 8 inserts an independent deterministic fail-closed authority boundary between every
Module 7 proposal and the one integrated EnergyPlus actuator. The controller selects an
action; `src/safety` independently decides whether it may become a `GuardedCommand`.
Neither a `ControlCommand`, an untyped mapping, nor a forged guarded object can reach the
physical writer. This is a local internal safety gate, not cybersecurity or formal proof.

```text
Module 7 ControlCommand -> ProposedCommand -> SafetyGuard -> GuardDecision
    -> GuardedCommandBuffer -> PhysicalWriteGate -> EnergyPlus writer
```

The only allowlisted identity is exactly `Zone Temperature Control / Cooling Setpoint /
SPACE3-1 / C`, zone `SPACE3-1`. Comparisons are exact and case-sensitive. `PLENUM-1`, all
other zones, aliases, wildcards, wrong units, and incomplete identities fail closed.

## Deterministic validation and recovery

Checks run in fixed order: enabled/shutdown state; API readiness, warmup and environment;
schema and command ID; duplicate identity; run/environment identity; monotonicity,
causality, validity and expiry; exact actuator/zone allowlists; type and finite-number
rules; absolute bounds; simulated-timestep rate bounds; then recovery and persistence.
Unknown errors never default to allow.

Outcomes are `ALLOW`, `CLAMP`, `HOLD_LAST_SAFE`, `RESET_TO_NATIVE`, and
`REJECT_NO_WRITE`. Every clamp records requested and applied values. Exact duplicates
return their original immutable result; conflicting duplicates reject. Reapplication of
an already guarded command preserves its guard-decision identity.

Independent `SafetyMemory` owns the last safe command, last proposal/decision, monotonic
state sequence, observed command IDs, run/environment identity, and shutdown/disabled
state. Stale values are never revived after TTL. Native reset uses EnergyPlus
`reset_actuator`; it never invents a restoration setpoint.

## Evidence-based bounds

Absolute limits remain 22.0–30.0 °C because those are the conservative Module 7 bounds
derived from the verified model, native/effective setpoints, and actuator evidence.
Marginal absolute violations up to 0.25 °C clamp; larger violations fail closed. The rate
limit is 1.61 °C per decision/timestep: direct inspection of the verified Module 7 stream
found a maximum legitimate transition of 1.6000000000000014 °C (30.0 to 28.4 °C).
This tolerance admits nominal verified behavior while rejecting larger unapproved steps.

## Persistence and physical gate

Schema version 3 adds normalized safety decisions, violations, guarded commands, and
physical write attempts with foreign keys. The safety audit uses a separate SQLite file
from the high-volume controller/state database, preventing writer contention. Live control
commits each decision before eligibility for a physical write; no-write shadow auditing
uses deterministic 500-record transactions. Every live set/reset trace is linked to a
guard decision. Persistence failure produces `persistence_failure_fail_closed` and no
command.

## Verification results — 2026-07-26

The 50-case adversarial suite passed twice with fingerprint
`876ad4ea2d7ee05264324fd3ba0cb046deb925747a71a75f6f72d1f489efd1cf`.
Two complete offline replays each allowed all 35,040 nominal proposals unchanged, made
zero writes, and matched fingerprint
`d5e08d9e4e4b1a5ca298630c1474421eb1f1d979b4a971dce98b7eff762af0fa`.

Annual live shadow persisted 35,040 states and 175,200 safety decisions. The one approved
zone produced 35,040 `ALLOW` outcomes; 140,160 proposals for the other four evaluated
zones produced `REJECT_NO_WRITE`. It made zero set/reset calls and passed physical parity.

Annual guarded live control persisted 35,040 states, 35,040 `ALLOW` decisions plus one
`RESET_TO_NATIVE` shutdown decision, 51,538 guarded set attempts, and one guarded reset.
All 51,539 physical attempts link to valid guard decisions. EnergyPlus exited zero with
zero warnings, severe/fatal errors, or API/callback/subscriber/persistence/guard errors.
SQLite integrity was `ok` with zero foreign-key violations. Module 7 and Module 8 setpoint,
controller, temperature, facility-electricity, and HVAC-electricity results were identical;
that is transparent-gate diagnostic parity, not evidence of savings or optimality.

## Commands

```powershell
.\.venv\Scripts\python.exe scripts/run_safety_challenges.py --output data/output/module_8_safety_guard/challenges/run_1/safety_challenge_report.json
.\.venv\Scripts\python.exe scripts/replay_safety_guard.py --output data/output/module_8_safety_guard/replay/run_1/safety_replay_report.json
.\.venv\Scripts\python.exe scripts/run_safety_shadow.py
.\.venv\Scripts\python.exe scripts/run_guarded_controller.py
.\.venv\Scripts\python.exe scripts/sync_safety_write_attempts.py
.\.venv\Scripts\python.exe scripts/validate_safety_guard.py
.\.venv\Scripts\python.exe scripts/compare_safety_runs.py
.\.venv\Scripts\python.exe scripts/inspect_safety_guard.py --query summary
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/verify_safety_guard.ps1
```

The two annual EnergyPlus runs require several minutes each; the full artifact verifier is
much faster because it validates completed live evidence without rerunning EnergyPlus.

## Limitations

The guard protects only the currently integrated `SPACE3-1` cooling-setpoint path. It does
not prove policy optimality, energy/cost/carbon savings, comfort improvement, universal
HVAC safety, or production readiness, and it does not replace EnergyPlus equipment safety.
Future actuators need independent discovery, approval, evidence-based bounds, and tests.
No LLM, MCP, network controller, comfort-debt logic, or optimization was added. Thermal
comfort remains a separate quantitative concern. The final annual command is right-censored
because no subsequent annual state exists.
