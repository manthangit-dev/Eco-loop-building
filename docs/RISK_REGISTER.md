# Risk Register

Module 15 remains a local demo, not production hosting. Scientific limits include the
three-hour window, electricity increase, unavailable demand model, and 41.67% coverage.

Module 14A remains a three-hour result; peak HVAC power was unavailable and interval coverage was 41.67%.

Module 12C residual risks remain explicit: demand is unavailable, 12-step thermal MAE is 0.892340 C, advisory and MicroTwin rankings disagree, and neither savings nor comfort improvement is verified.

- MicroTwin model error/OOD: expose empirical uncertainty and OOD metadata; do not rank unqualified models.
- Proxy overclaiming: label outputs offline surrogate estimates, keep demand unavailable, and prohibit verified-savings/guaranteed-comfort claims.

- Small-model tool omission: fail successful completion until objective-required evidence exists; allow one correction and an explicitly audited permitted-tool prefetch only.

- Replay false confidence: require executable fixture classification, concrete mutation metadata, exact reason codes, coverage-gap validation, and two deterministic runs.

Module 8 mitigations: raw/forged command bypass is blocked at runtime; audit failure fails
closed; exact identity and unit mismatches reject; stale/future/expired commands reject;
rate and absolute limits are deterministic; cleanup reset is independently guarded. Residual
risks remain single-building scope, bounds tied to current evidence, SQLite write latency,
right-censored final outcome, lack of comfort quantification, and over-interpreting diagnostic
parity as safety proof, optimization, or savings.

| Risk | Probability | Impact | Detection method | Mitigation | Fallback |
| --- | --- | --- | --- | --- | --- |
| Windows 10 incompatibility with EnergyPlus 26.1 | Medium | High | Install/run check in Module 1 | Prefer supported host and document compatibility | Use configured WSL/Linux platform |
| EnergyPlus version mismatch with IDF | Medium | High | Version and model validation run | Pin 26.1.0 and preserve originals | Use a compatible documented model copy |
| Missing actuator handles | Medium | High | Enumerate handles in Module 5 | Validate target names before control | Run fallback without unavailable actuator |
| Missing output-variable handles | Medium | High | Sensor discovery log | Make required/optional map explicit | Mark unavailable and use safe reduced state |
| PMV unavailable in initial model | High | Low | Output-variable discovery | Treat PMV as optional | Operate without PMV |
| CO2 unavailable in initial model | High | Low | Output-variable discovery | Treat CO2 as optional | Operate without CO2 |
| LLM timeout | Medium | Medium | Timeout metrics | Bound request time and prompt size | Deterministic fallback |
| Invalid LLM JSON | Medium | Medium | Schema validation | Pydantic structured validation | Reject and use fallback |
| Unsafe LLM values | Medium | High | Safety-guard logs | Range, rate, and fairness checks | Reject and use fallback |
| Control oscillation | Medium | High | Trend and action-delta monitoring | Hysteresis and rate limits | Hold safe set-point/fallback |
| Long simulation logs | Medium | Low | Log size monitoring | Rotation and selected telemetry | Archive or summarize logs |
| Excessive prompt size | Medium | Medium | Token/size measurements | Compact state summaries | Use minimal deterministic context |
| Slow local LLM inference | High | Medium | Cycle latency measurement | Select model after hardware check | Deterministic fallback |
| Insufficient RAM or GPU | Medium | Medium | Hardware inspection | Choose smaller compatible model | Run without LLM |
| Non-reproducible external APIs | Medium | High | Input provenance audit | Use local versioned CSV signals | Retain local fixture inputs |
| Baseline and controlled runs use different inputs | Medium | High | Manifest comparison | Lock shared input manifest | Invalidate and rerun comparison |
| Comfort savings trade-off | Medium | High | Occupied comfort metrics | Debt ledger and guard constraints | Prioritize comfort-first fallback |
| Generated result files accidentally committed | Medium | Medium | Git status/review | `.gitignore` and output separation | Remove from index; retain local copy |
| Codex implements modules out of sequence | Medium | Medium | Module-plan review | Persistent AGENTS.md rules | Stop, revert scoped changes safely |
| Python 3.12 launcher is unavailable or inaccessible | High | High | `py -3.12 --version` and environment checker | Install or repair Python 3.12 and recreate `.venv` | Use a supported WSL Python 3.12 environment |
| `ENERGYPLUS_HOME` is unset or invalid | High | High | Module 1 environment checker | Configure local `.env` with the real installation directory | Install and verify EnergyPlus 26.1.0 on the selected platform |
| Source header names Chicago TMY2 while Module 2 requires Chicago O'Hare TMY3 | Medium | Medium | Compare IDF header, configured EPW filename, and manifest checksum | Record exact TMY3 provenance with every baseline result | Reject comparisons that do not use the manifest weather checksum |
| Baseline EnergyPlus warnings obscure validity | Low | High | Parse the authoritative final ERR summary | Require zero severe/fatal errors and report every warning | Keep Module 2 incomplete until reviewed; verified run produced zero warnings |
| EnergyPlus API wrapper assumptions differ from the installed build | Medium | High | Inspect installed objects and signatures | Use observed 26.1 signatures and report the loaded CDLL path | Keep Module 3 incomplete if a required callable is absent |
| Runtime API timeout cannot safely hard-kill an in-process C call | Medium | High | Watchdog timing and cleanup metadata | Request `stop_simulation`, preserve partial outputs, and wait before deleting state | Restart the runner process after diagnosis; never delete a live state |
| `Electricity:Facility` is listed but returns an invalid live handle in EnergyPlus 26.1 | High | Medium | Persist runtime API discovery and handle manifest | Use verified `ElectricityPurchased:Facility` for this no-generation baseline and retain the failed aggregate as optional diagnostics | Re-evaluate the exact meter if onsite generation or EnergyPlus version changes |
| Unoccupied plenum has no occupant-count runtime key | High | Low | Cross-check API listing and model `People` objects | Configure a documented zero only for `PLENUM-1`; require handles for occupied zones | Remove the fallback if occupancy is added to the plenum |
| Actuator callback repeats within one zone timestep | High | Low | Count set calls and unique simulation periods | Reapply only the same bounded value and distinguish set calls from unique periods | Revisit timing if a future control strategy requires zone-only writes |
| External override is not released | Low | High | Require reset event and post-reset set-point recovery | Call `reset_actuator` after the window and during active-state cleanup if needed | Fail validation and stop before autonomous control |
| SQLite throughput or queue backpressure | Medium | High | Queue high-water, delay, timeout counters | Bounded queue, batching, WAL | Fail rather than silently drop state |
| State subscriber failure | Medium | Medium | Subscriber error counter | Execute outside lock and isolate exceptions | Unsubscribe failed consumer |
| Database corruption or incomplete shutdown | Low | High | Integrity/FK checks and drained metadata | Dedicated owner thread and ordered close | Reject DB and replay Module 4 JSONL |
| WAL sidecars after interruption | Medium | Medium | Output/Git inspection | Ignore generated DB artifacts | Archive or safely checkpoint the directory |
| Sequence or schema mismatch | Low | High | Constraints and validation | Reject duplicates/decreases/unsupported versions | Future explicit migration only |
| Large annual database (~499 MB) | High | Medium | File-size monitoring | Generated output exclusion | Revisit retention in a future module |
| Future concurrent readers | Medium | Medium | Busy-time and reader tests | WAL and read-only predefined queries | Serialize or redesign later |
| Generated database committed | Medium | High | Git status and ignore checks | Ignore DB, WAL, SHM, output trees | Remove from index; retain locally |
| Fallback oscillation or incorrect hysteresis | Medium | High | Mode/reason and hold-transition validation | Explicit 0.5°C hysteresis and four-step hold | Reset to native control |
| Stale command reuse or state-command causality error | Low | High | TTL, source/effective sequences, replacement statistics | Bounded latest buffer and next-sequence commands | Expire/clear and reset |
| Occupancy transition or missing baseline setpoint | Medium | High | Grace counters and availability records | Four-step grace; fail closed when baseline is absent | Native EnergyPlus control |
| Controller queue delay or database growth | High | Medium | Queue/size monitoring | Batches of 100 and bounded queue | Stop rather than drop decisions |
| Incomplete actuator reset | Low | High | Reset event and post-run validation | Explicit shutdown reset | Mark run failed and rerun |
| False confidence before Module 8 | Medium | High | Required pending marker and forbidden-claim scan | State that only minimal invariants exist | Do not accept LLM actions |
| MCP bypasses safety | Low | High | Catalogue and write-audit checks | Disable control; dry-run without writer | Fail closed |
| MCP opens a listener | Low | High | Subprocess smoke inspection | Stdio-only transport | Reject non-local transport |
| Unbounded MCP response | Medium | Medium | Limit/schema tests | Fixed row/history limits | Structured bounded error |
| Local model missing | High | Low | Runtime/model discovery | Keep mock evidence clearly labeled | Install reviewed model; rerun smoke |
| Prompt-injected control request | Medium | High | Denied-tool tests | Code-owned allowlist and override-field rejection | Fail session closed |
| Hallucinated evidence or savings | Medium | High | Evidence reconciliation | Reject unknown IDs and unsupported claims | Return validation error |
| Documented CLI drifts from implementation | Medium | Medium | Subprocess command audit | Stable wrappers, help, and one-command demo | Fail demo step with log path |
| Diagnostic electricity difference interpreted as savings | Medium | High | Terminology/documentation review | Label as experimental association only | Withhold savings claims until comparable Module 19/20 experiments |
# Module 10B residual risk

Module 11 forecasts are demonstration scenarios, not live data. Plans have no physical
trajectory model; every future action requires later execution-time guard validation.

The 0.6B model can produce vague or contradictory summaries. Mitigation is strict
tool policy, request-bound typed arguments, evidence reconciliation, no exposed
control-capable tool, Module 8 dry-run validation, and deterministic zero-write
auditing. No model output can directly reach EnergyPlus.
# Module 13 risks and controls

- **Accounting metaphor mistaken for energy:** RTFU labels and response validation block kWh/storage claims.
- **Aggregate fairness mistaken for individual fairness:** no identities or personal/health data are accepted; claims remain zone/event/temporal aggregates.
- **LLM alters authoritative values:** deterministic results are pre-fetched and validated; altered debt, balance, or equity is rejected.
- **Advisory result causes control:** no execution tool was enabled and physical-write deltas are verified as zero.
- **Unsupported comfort claims:** boundaries are documented assumptions and verified improvement is not claimed.

# Module 14 risks and controls

- **Approval drift/replay:** fingerprints, expiry, mode binding, checksums, limits, and one-time consumption fail closed.
- **Writer bypass:** only Module 8-created `GuardedCommand` reaches the existing physical gate; zero unguarded writes were observed.
- **Orphan override:** mandatory reset runs at normal or fallback termination; completion is blocked without it.
- **Short result overclaim:** documentation labels results scenario-specific and explicitly rejects annual/real-world inference.
- **Prediction mismatch:** 8.742725 °C reconciliation MAE and 0% coverage are retained as a limitation.
