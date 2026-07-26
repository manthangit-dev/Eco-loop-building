# Acceptance Criteria

Module 15 passed snapshot provenance, loopback/read-only policy, local assets, security and
accessibility checks, deterministic export/replay, clean shutdown, and zero-write checks.

Module 14A requires exact alignment, non-native effect, guarded reset, valid reconciliation, and no annual run.

Module 12 acceptance is complete after the Module 12C audit reached zero gaps with all final fixtures dedicated and mutation-sensitive and with zero physical-control deltas.

Module 12 acceptance requires a thermal surrogate that beats persistence on the chronological held-out test, bounded 3/6/12-step validation, safe reproducible artifacts, all eligible Module 11 rollouts, schema-v7 persistence, six bounded MCP tools, zero EnergyPlus starts, and zero physical writes. Demand is permitted to remain honestly unavailable when it fails qualification.

Module 12A required-evidence sessions and repository validation passed, but closure remains incomplete until category-level replay checks are replaced by meaningful dedicated fixtures for every applicable negative scenario.

Modules 0 through 9 are complete. Module 10 is incomplete pending real-model smoke.
A deterministic isolated-zone test acquired one

Module 10A acceptance covers runtime command repair and the recorded one-command demo only.
The default demo passes without Ollama, starts no EnergyPlus process, performs zero writes,
and leaves `propose_guarded_control` disabled.
cooling-setpoint handle, applied a bounded override, observed the response, reset the
actuator, and verified normal control recovery. Autonomous control and later criteria
remain future work.

Module 6 acceptance is met: full replay and a real annual sensing-only run each
persisted 35,040 canonical states and 210,240 zone rows, drained bounded queues, passed
SQLite integrity/foreign-key checks, and recorded no actuator or control access. This
is storage evidence, not an energy-saving result.

Module 7 acceptance is met: repeated annual replay was deterministic, live shadow made zero
writes and preserved physical parity, and annual live fallback used one approved actuator
with causal commands, bounded state, hysteresis/hold/grace behavior, observed response, and
shutdown reset. Module 8 acceptance is met: an independent typed/runtime gate blocks raw
and forged commands, repeated challenge/replay fingerprints match, annual safety shadow
made zero writes with physical parity, and all 51,539 annual live set/reset attempts link
to persisted guard decisions with zero bypasses or guard errors.

## Required MVP acceptance criteria

| Area | Measurable criterion |
| --- | --- |
| Environment setup | Documented, reproducible environment validates supported Python and EnergyPlus versions. |
| Baseline simulation | The selected IDF completes a representative baseline run with declared inputs. |
| Python runner | A runner starts and observes EnergyPlus without hard-coded local paths. |
| Sensor extraction | Required sensor values are captured for each control interval; unavailable optional values are explicitly reported. |
| Actuator injection | Validated cooling set-point action is injected and its response is observed. |
| Fallback controller | A deterministic fallback supplies a valid action when the LLM is unavailable. |
| Safety guard | 100% of structurally invalid or unsafe proposed actions are rejected. |
| Comfort-debt ledger | Per-zone debt is persisted and influences candidate assessment. |
| Flexibility scoring | A per-zone temporary flexibility score is calculated and logged. |
| Thermal battery | Pre-cool, coast, and restoration behavior is evaluated through real simulation. |
| Candidate selection | Three strategy candidates are evaluated before an action is selected. |
| Ollama integration | A locally available model returns structured proposals or failure is handled safely. |
| MCP tools | Structured MCP-compatible tools expose only bounded planner capabilities. |
| Critic/self-correction | Observed outcomes produce auditable feedback for a subsequent cycle. |
| Failure handling | Timeout, malformed JSON, invalid values, and missing handles trigger logging and fallback. |
| Dashboard | Streamlit displays stored real run data and labels unavailable data. |
| Baseline comparison | Identical inputs and periods are recorded for separate baseline and AI runs. |
| Final experiments | A representative-week comparison produces traceable metrics. |
| Documentation | Configuration, assumptions, commands, and limitations are current. |
| Demonstration video | The video shows a real representative-day control loop and limitations. |

## Performance targets

Module 9 acceptance is met by real stdio discovery of the fixed 18-tool catalogue,
matching repeated 24-call replays, fail-closed structured errors, Module 8 dry-run
validation without a writer, disabled control, and passing audit integrity checks.

- At least 10% energy reduction, at least 10% peak-demand reduction, at least 95% occupied comfort compliance, and at least 98% successful control cycles.
- These are targets only. They must be measured from real comparable simulations before being reported as achieved.

## Stretch goals

- Simultaneous baseline/AI instances, PMV and CO2 support where the model exposes them, and broader actuator coverage.
# Module 10 result

Module 11 passes trusted-field preflight, 66-case repeated deterministic replay,
schema-v6 persistence, 24-tool MCP catalogue, three real local-model planning sessions,
and zero-write validation. It does not claim savings or implement the MicroTwin.

Module 10 acceptance is complete with local `qwen3:0.6b`: provider health,
native tool calling, recorded MCP evidence, dry-run Module 8 validation, denied
control, audit persistence, and zero new physical writes all passed.
# Module 13 acceptance criteria

- Five qualified Module 12 rollouts are evaluated deterministically without EnergyPlus or actuator writes.
- Comfort burden, credit/debt, fairness, equity, and RTFU bank values are finite and fail closed.
- Schema 8 is additive, idempotent, integrity-clean, and foreign-key-clean.
- All 156 required replay scenarios use registered fixtures, execute production code, and pass twice identically.
- Mock and three real-model advisory sessions use MCP evidence and make no physical writes.
- False kWh, guaranteed comfort, verified savings, execution, or altered authoritative-value claims are blocked.
- Focused and complete tests, Ruff, mypy, configuration validation, and fast/full verification pass before completion is declared.

# Module 14 acceptance result

All 53 Module 14 criteria passed: exact approval binding and one-time consumption; deterministic state/scheduling; trusted live state; Module 8-only guard authority; existing writer only; mandatory reset; zero-write replay/shadow; one guarded live set and reset; compatible comparison and reconciliation; four read-only MCP tools; schema 9 integrity; 130 replay scenarios with zero gaps; 536 tests; Ruff and strict mypy; unchanged canonical checksums; zero annual runs; and unstaged changes.
