# Decision Log

## Module 15

Use the Python standard-library server and local assets. HTTP reads a validated snapshot
and cannot rebuild evidence or reach planning, approval, execution, MCP, LLM, or EnergyPlus.

## Module 14A

Path B uses a derived July 19 IDF because the original July 21 Sunday horizon was unoccupied.

## Module 12C

The final 25 shared-only requirements were promoted to dedicated executable fixtures. Strict coverage acceptance now precedes any final verifier PASS.

- Module 12 uses deterministic ridge ARX with chronological splits and persistence qualification. A causal lag-change repair was accepted after the first thermal fit failed; the final thermal model qualifies. The whole-HVAC demand proxy remains unavailable because it failed its baseline comparison.

- Module 12A reuses the qualified artifact and enforces mandatory evidence in the supervisor. A single correction plus read/proposal-only supervisor prefetch was chosen because the small local model sometimes answers without tools; execution mode is retained in every tool step.

- Module 12B replaces provisional negative category checks with production-path fixture factories and schema-v2 manifest metadata. The qualified model and persisted real-model sessions are reused unchanged.

Module 10A runtime decision (2026-07-26): use deterministic recorded-run discovery and
generated request files behind stable subprocess-tested CLIs. Suppress harmless MCP child
stderr at the client boundary so Windows PowerShell 5 does not treat SDK diagnostics as a
failed step. The one-command demo remains zero-write and EnergyPlus-free.

Module 10 decision (2026-07-26): use a provider protocol, deterministic mock, and
loopback-only Ollama adapter without proxy/cloud fallback. Code owns six iterations, six
tool calls, two corrections, and the denylist. Schema-v5 auditing is additive. No Ollama
runtime/model was found, no download occurred, and real-model acceptance remains incomplete.

Module 9 completion record (2026-07-26): official Python MCP SDK 1.28.1 serves a fixed
18-tool catalogue over local stdio. Sixteen tools are read-only, one runs Module 8
validation without a writer, and the control-capable tool is disabled. Repeated 24-call
replays and a real subprocess smoke passed with zero physical writes. The additive
schema-v4 audit passed integrity and foreign-key checks. No EnergyPlus run or LLM was used.

Module 9 implementation plan (2026-07-26): use the official Python MCP SDK over local
stdio only; add schema-versioned immutable request/response models, deterministic
serialization and bounded pagination; register a fixed catalogue of read-only,
proposal-only, and disabled-by-default control-capable tools backed by persisted Modules
6–8 evidence; route dry-run proposals through a fresh Module 8 guard without any writer;
store calls in an additive schema-v4 MCP audit database; then verify deterministic replay
and a real stdio subprocess smoke test without starting EnergyPlus. Module 8 remains the
exclusive physical authority boundary.

Module 8 implementation plan (2026-07-26): create a separate `src/safety` package with
immutable proposal, guard-decision, and guarded-command types; apply deterministic identity,
phase, causality, freshness, value, rate, duplicate, and recovery checks; own independent
guard memory; add an additive schema-v3 audit migration; require runtime-validated guarded
commands at the physical writer; then pass unit and adversarial tests before annual replay,
live-shadow, and guarded-live verification. Module 7 policy behavior remains unchanged.

Module 8 completion record (2026-07-26): use an exact one-actuator allowlist, 22–30 °C
absolute bounds, and a 1.61 °C simulated-timestep rate limit supported by the observed
1.6000000000000014 °C maximum Module 7 transition. Separate schema-v3 safety auditing from
the controller database to avoid writer contention. Two 50-case challenges and two annual
replays were deterministic; annual shadow and guarded live control passed with 51,539
guard-linked physical attempts and zero bypasses/errors. Broader actuators remain rejected.

| ID | Date | Decision | Reason | Alternatives rejected | Revisit condition |
| --- | --- | --- | --- | --- | --- |
| D-001 | 2026-07-25 | Use EnergyPlus 26.1.0 | Frozen MVP target | Unpinned/latest version | Compatibility issue with chosen model/platform |
| D-002 | 2026-07-25 | Use Python 3.12 | Frozen MVP target | Other Python versions | Dependency compatibility requires change |
| D-003 | 2026-07-25 | Start with a five-zone office | Manageable fairness scenario | Single zone or complex building | Model cannot support required controls |
| D-004 | 2026-07-25 | Use 15-minute control intervals | Balances responsiveness and stability | Shorter or longer intervals | Real experiments show instability or missed peaks |
| D-005 | 2026-07-25 | Cooling set-point is primary actuator | Clear initial control surface | Other HVAC actuators | Actuator unavailable or ineffective |
| D-006 | 2026-07-25 | Ventilation multiplier is secondary | Secondary flexibility option | Wider actuator set | Model/handles do not support it |
| D-007 | 2026-07-25 | Use local CSV external signals | Reproducibility | Live external APIs | Better reproducible approved source is available |
| D-008 | 2026-07-25 | Run baseline and AI sequentially | Identical-input comparison is simpler | Dual live instances | Stretch goal becomes necessary and validated |
| D-009 | 2026-07-25 | Use Streamlit dashboard | Fast prototype visualization | Other dashboard frameworks | UX needs exceed Streamlit scope |
| D-010 | 2026-07-25 | Use SQLite storage | Local, simple, reproducible storage | Remote database | Scale or concurrency requires change |
| D-011 | 2026-07-25 | Use Ollama runtime | Local open-source LLM route | Hosted LLM service | Hardware/runtime makes it unsuitable |
| D-012 | 2026-07-25 | Postpone exact LLM model | Hardware is unknown | Premature model selection | Hardware inspection completes |
| D-013 | 2026-07-25 | Separate LLM proposals from deterministic safety | Prevent direct unsafe actuation | Direct LLM control | Never for MVP safety boundary |
| D-014 | 2026-07-25 | PMV and CO2 are optional pending verification | Initial model may not expose them | Treating them as required | Model capability is verified |
| D-015 | 2026-07-25 | Use native Windows for the current Module 1 verification attempt | The current runtime reports Windows; no WSL kernel marker is present | Assuming WSL or Linux without evidence | Verification moves to a different host/runtime |
| D-016 | 2026-07-25 | Preserve the EnergyPlus 26.1 five-zone example and add only SQLite reporting to the derived baseline | Both the byte-identical source smoke run and reporting-only baseline completed against the official Chicago O'Hare TMY3 file with zero warnings, severe errors, or fatal errors | Editing physical inputs or adding unverified outputs | A later approved module requires a separately derived model |
| D-017 | 2026-07-25 | Run Module 3 through the installed EnergyPlus Runtime API with lifecycle-only callbacks | The real API run exited zero, cleaned its fresh state, passed output validation, and produced a byte-identical primary CSV to Module 2 | Subprocess simulation, state reuse, exchange/actuator callbacks | A later approved module adds bounded sensing |
| D-018 | 2026-07-25 | Use end-of-zone-timestep read-only extraction with explicit runtime discovery | The annual run produced 35,040 validated weather snapshots with zero callback/API errors and no actuator access | Polling, warmup/design-day rows, in-memory annual storage | A later approved module changes observation timing |
| D-019 | 2026-07-25 | Use `ElectricityPurchased:Facility` as the required facility meter and a verified zero for unoccupied `PLENUM-1` | EnergyPlus 26.1 advertises `Electricity:Facility` but returns handle `-1`; the baseline has no generation, and the plenum has no `People` object/key | Claim invalid handles, fabricate nonzero occupancy, modify the IDF | Model generation or plenum occupancy is introduced, or the API aggregate handle becomes valid |
| D-020 | 2026-07-25 | Use the isolated `SPACE3-1` Zone Temperature Control cooling-setpoint actuator for a fixed July 19 test | Real discovery found five eligible actuators; Module 4 data ranked SPACE3-1 highest at the hottest occupied summer-afternoon record | Shared schedules, plenum/equipment/weather actuators, arbitrary CLI selection | The model or actuator catalog changes |
| D-021 | 2026-07-25 | Apply 24.9°C with `after_predictor_before_hvac_managers` and release via `reset_actuator` | The control run measured 23.9°C; +1.0°C produced a verified response and recovery with zero API/callback errors | Guessed restoration value, extreme override, autonomous policy | A later approved control module introduces separately validated policy logic |
| D-022 | 2026-07-25 | Use immutable schema-v1 states, a 256-state bus, and a dedicated 512-entry SQLite writer queue | Replay and live annual runs each persisted 35,040 states without loss; integrity and foreign keys passed | Unbounded memory, callback-thread writes, external database | Throughput or concurrency exceeds local needs |
| D-023 | 2026-07-25 | Preserve EnergyPlus API minute values through 99 | Validated replay/live data contains floating-point-derived minute values up to 68 | Rewrite timestamps or reject valid observations | A normalized EnergyPlus timestamp API is available |
| D-024 | 2026-07-25 | Use a deterministic per-zone state machine with four-timestep hold/grace, 0.5°C hysteresis, and two-sequence command TTL | Two annual replays matched and annual live modes completed without state loss or controller errors | Random/stateless control, unbounded stale commands, tariff/carbon optimization | Module 8 guard or later measured policy requirements change the approved bounds |
| D-025 | 2026-07-25 | Restrict real fallback control to the Module 5 verified `SPACE3-1` cooling-setpoint actuator | Annual live control used exactly one identity, produced observed 28.4–30.0°C setpoint response, and reset at shutdown | Multi-zone or arbitrary actuator execution | Independent Module 8 safety validation authorizes broader control |
# Module 10B — local model selection

Module 11 uses local versioned scenarios and dimensionless lower-is-better advisory
scores. Deterministic selection is authoritative fallback; LLM selection is advisory.

Selected `qwen3:0.6b` as the final low-resource fallback because available RAM
before installation was about 437 MiB. Official Ollama 0.32.4 reported a 522 MB
model. Deterministic evidence remains authoritative over small-model prose.
# Module 13 decisions

- Use RTFU as a relative accounting unit; never present it as kWh or physical storage.
- Use explicit demo comfort boundaries because no approved preference source exists.
- Preserve Module 12 plan eligibility and add ledger ranking as advisory evidence.
- Keep debt forgiveness and direct balance mutation absent from MCP.
- Persist through additive schema 8 and retain deterministic fallback behavior without the LLM.

# Module 14 decisions

- Require explicit local simulation-only approval for every non-replay mode.
- Bind approvals to exact artifacts, environment, actuator, values, limits, expiry, and checksums.
- Retain Module 8 as execution-time authority and the existing writer as the sole actuator route.
- Use relative action offsets with newly constructed live timestamps.
- Report the observed 0 J result only as a short-window simulation difference.
- Preserve poor reconciliation evidence rather than retraining or hiding it.
