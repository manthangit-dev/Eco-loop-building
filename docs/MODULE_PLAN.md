# Module Plan

Module 15 is complete: read-only dashboard, provenance explorer, deterministic evidence
package, 120-scenario replay, and hackathon demo. No later module began.

Module 14A is complete with exact-window repair and three bounded aligned runs. Module 15 was not started.

Module 12 is complete after Module 12C executable-coverage closure. Module 13 remains pending and was not started.

- Module 12: offline MicroTwin candidate evaluation — **Incomplete**. Required-tool sessions and repository validation pass, but several replay entries currently share category-level checks instead of dedicated negative fixtures. They must not be accepted as meaningful closure coverage yet.

Modules 0 through 9 are completed. Module 10 is implemented but incomplete pending a real
installed-model smoke. No later module may be implemented early.

Module 10A runtime audit/demo is complete: repaired CLIs dynamically select recorded data,
run the real stdio MCP boundary and mock supervisor, and demonstrate two Module 8 dry runs
with zero physical writes. It does not satisfy Module 10's missing real-model criterion.

| # | Module / status | Purpose | Inputs | Expected outputs | Dependencies | Tests or verification | Definition of done |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | Scope and repository foundation — **Completed** | Freeze MVP scope and scaffold repository | Project brief | Rules, docs, config, directories | None | File tree; YAML parse; documentation review | Required foundation exists and contains no functional code |
| 1 | Development environment — **Completed** | Prepare reproducible local environment | Version decisions, host details | Documented environment and path configuration | 0 | Validate Python/EnergyPlus discovery | Prerequisites are verified and documented |
| 2 | Baseline EnergyPlus building — **Completed** | Establish baseline office model | Original IDF, weather | Preserved source and runnable derived setup | 1 | Real baseline run | Model runs with declared inputs |
| 3 | Python EnergyPlus runner — **Completed** | Launch and coordinate simulation | Environment, model | Minimal runner interface | 1, 2 | Executed runner check | Runner starts simulation reproducibly |
| 4 | Live sensor extraction — **Completed** | Read declared state | Running simulation, sensor map | Timestamped structured observations | 3 | Compare reads to output records | Required available sensors are captured |
| 5 | Actuator injection — **Completed** | Apply validated controls | Handles, safe action | Observed actuator effect | 3, 4 | Handle and response check | Primary actuator injection works safely |
| 6 | State bus and storage — **Completed** | Normalize and persist state | Observations | Canonical state bus and SQLite records | 4, 5 | Full replay, live annual run, integrity checks | Each mode persisted 35,040 states and 210,240 zone rows |
| 7 | Rule-based fallback controller — **Completed** | Provide LLM-independent control | Canonical state, policy limits | Deterministic causal cooling commands | 6 | Repeated replay, live shadow, annual one-zone control | Verified fallback operates without LLM; Module 8 guard remains pending |
| 8 | Safety guard — **Completed** | Enforce control constraints | Proposed actions, state | Guard decision and guarded command | 5–7 | 50-case challenges, repeated replay, annual shadow/live | All physical writes are guard-linked; invalid actions fail closed |
| 9 | Local MCP server and deterministic building tool layer — **Completed** | Expose bounded recorded evidence and guarded dry runs | Modules 6–8 artifacts | Local stdio MCP catalogue and audit | 6–8 | Replay and subprocess smoke | 18 tools; control disabled; zero writes |
| 10 | Local LLM adapter and controlled MCP supervisor — **Incomplete** | Bounded advisory local-model tool use | Module 9 tools | Typed recommendation and schema-v5 audit | 8–9 | Mock replay and real-model smoke | Mock passes; installed-model smoke required |
| 11 | Thermal-battery strategy — Pending | Plan pre-cool/coast/restore | Signals, state, scores | Strategy candidates | 8–10 | Scenario simulation checks | Three phases are evaluated safely |
| 12 | Candidate-action tournament — Pending | Compare strategy variants | Candidate actions, metrics | Selected ranked candidate | 9–11 | Ranking and tie-break tests | Comfort-first, balanced, aggressive candidates compare |
| 13 | Ollama and local LLM — Pending | Obtain structured local proposals | Hardware inspection, state | Parsed proposal or safe error | 7, 8, 12 | Local request and failure tests | Model choice documented; failures safe |
| 14 | MCP tool server — Pending | Expose bounded planner tools | State and evaluation interfaces | MCP-compatible tool layer | 6, 12, 13 | Tool schema tests | Tools have validated inputs/outputs |
| 15 | Agent orchestration — Pending | Coordinate planning cycle | LLM, tools, guard | Ordered orchestrated cycle | 8, 13, 14 | End-to-end mocked cycle | No LLM bypasses guard |
| 16 | Critic and self-correction — Pending | Learn from observed outcome | Outcome records, proposals | Auditable feedback | 6, 15 | Feedback linkage tests | Feedback informs later planning without bypassing safety |
| 17 | Failure handling — Pending | Handle expected operational faults | Exceptions, timeouts, failures | Recoverable error paths | 7, 8, 15 | Fault injection tests | Fallback and logging activate reliably |
| 18 | Logging and observability — Pending | Make cycles diagnosable | Events, metrics | Structured logs and traces | 6, 17 | Log completeness review | Decisions and failures are auditable |
| 19 | Baseline-versus-AI execution — Pending | Run comparable experiments | Shared manifest, controller | Separate baseline/AI runs | 2, 15, 18 | Input-manifest comparison | Runs use identical declared inputs |
| 20 | Quantitative metrics — Pending | Compute outcome metrics | Comparable run data | Energy, peak, comfort, reliability, fairness metrics | 19 | Hand-checked metric fixtures | Metrics are reproducible and labeled |
| 21 | Streamlit dashboard — Pending | Present real stored evidence | Metrics and records | Dashboard views | 18, 20 | Manual dashboard validation | No fabricated data; limitations visible |
| 22 | Automated testing — Pending | Strengthen regression coverage | Existing modules | Test suite and coverage intent | 1–21 | Executed tests | Relevant functional behavior is covered |
| 23 | Experiment scenarios — Pending | Define fair test cases | Weather, signals, model | Scenario manifests | 19, 20 | Reproducibility review | Scenarios are documented and runnable |
| 24 | Documentation — Pending | Finalize technical narrative | Implemented evidence | Updated docs and runbook | 1–23 | Documentation cross-check | Claims match executed evidence |
| 25 | Presentation and demonstration — Pending | Produce hackathon delivery | Real results, dashboard, docs | Demo and presentation artifacts | 20, 21, 24 | Rehearsed demonstration | Demo accurately represents prototype limits |

For every pending module, its definition of done additionally requires: requested scope only, relevant validation executed, honest reporting, and affected documentation updated.
# Module 10 completion note

Module 11 is complete as an advisory-only forecast and candidate-planning layer.
Module 12 remains pending.

Module 10 is complete after official local Ollama generation, native tool calling,
four recorded-data sessions, persisted denial of the control-capable tool, and a
zero-write comparison. Module 11 remains pending and was not started.
# Module 13 — Comfort Ledger and Thermal Bank

Scope: deterministic comfort accounting, RTFU bank accounting, equity-aware ranking, schema-8 persistence, MCP read/proposal tools, claim validation, replay coverage, and mock/real-model advisory demonstrations. Module 14 control work is explicitly out of scope.

# Module 14 — Approval-gated simulation execution

Completed scope: exact preflight and approval binding, four execution modes, state machine, scheduler, trusted live state, Module 8 guard integration, existing writer integration, fallback/reset policy, schema 9, four read-only MCP tools, 130-scenario replay, and three bounded EnergyPlus integrations. Module 15 was not started.
