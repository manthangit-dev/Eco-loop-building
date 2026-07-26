# Module 11 planning engine

Module 15 reads persisted contexts, candidates, and rankings; it cannot generate plans.

Module 14A reused unchanged weights/actions and deterministically selected cooling-relevant state 19147.

Module 12 consumes the unchanged eligible candidate set and shared planning context. It applies candidate setpoint trajectories to predicted state recursively; actual future telemetry is never used. Advisory and MicroTwin rankings are stored and compared independently.

Module 11 is an advisory-only deterministic planning layer. It combines one
committed recorded state with versioned local weather, expected occupancy,
tariff, carbon, and building-event scenarios. Future recorded temperatures,
energy, controller outcomes, and safety outcomes are prohibited as forecast
inputs. The files are simulation scenarios, not live services.

`PlanningContext` is immutable and fingerprinted. The demonstration uses a
12-timestep (180-minute) horizon at the repository's 15-minute zone timestep.
Six templates are implemented: native hold, comfort first, balanced,
precondition before peak, vacancy relaxation, and occupied recovery. Templates
are emitted only when their deterministic conditions apply.

Candidate actions contain no physical authority. Every action is advisory and
requires execution-time Module 8 revalidation. Only the first immediately
applicable action is dry-run checked; no `GuardedCommand` is retained and no
writer is called. Scores are dimensionless advisory penalties (intervention,
churn, occupancy risk, peak alignment, uncertainty, missing data, and guard
rejection), with lower scores preferred and stable strategy/ID tie-breaking.
They are not kWh, cost, carbon, temperature, savings, or comfort predictions.

Six MCP tools expose context, generation, evaluation, comparison, session
inspection, and advisory selection. Selection accepts only an existing eligible
candidate in the same deterministic set. `propose_guarded_control` remains
disabled. The local LLM can recommend but cannot create or modify a candidate.

```powershell
.\.venv\Scripts\python.exe scripts\validate_planning.py
.\.venv\Scripts\python.exe scripts\build_planning_context.py
.\.venv\Scripts\python.exe scripts\generate_candidate_plans.py
.\.venv\Scripts\python.exe scripts\compare_candidate_plans.py
.\.venv\Scripts\python.exe scripts\run_planning_mock_replay.py
.\.venv\Scripts\python.exe scripts\run_planning_real_smoke.py --pretty
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\run_planning_demo.ps1
```

Persistence uses schema version 6 with foreign keys and normalized contexts,
forecast points, plans, actions, score components, validation events, planning
sessions, and selections. Module 12's MicroTwin is not implemented here.

Verification measured 66/66 deterministic replay scenarios with identical repeated
fingerprint, five eligible candidates and seven actions, five first-action `ALLOW`
dry-runs, three passing real-model MCP sessions in 49.578 seconds, and zero new writes.
The fast verifier completed in 4.472 seconds and the full verifier in 13.991 seconds
while reusing the single completed 227-test/Ruff/Mypy software verification.
# Module 13 ranking

The planner's candidate set and Module 11/12 scores remain unchanged. The ledger evaluator adds deterministic burden, debt, fairness, equity, reserve, and bank terms, reports ranking disagreement explicitly, and selects only an eligible candidate. Selection remains advisory and cannot execute a plan.

# Module 14 boundary

The planner remains advisory. Module 14 binds one persisted action exactly, maps its relative offset onto new committed simulation timing, and rejects changed or inserted actions. Planning eligibility never replaces Module 8 execution-time validation.
