# Module Plan

Modules 0 through 5 are completed. Module 6 is next and remains pending; no later module may
be implemented early.

| # | Module / status | Purpose | Inputs | Expected outputs | Dependencies | Tests or verification | Definition of done |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | Scope and repository foundation — **Completed** | Freeze MVP scope and scaffold repository | Project brief | Rules, docs, config, directories | None | File tree; YAML parse; documentation review | Required foundation exists and contains no functional code |
| 1 | Development environment — **Completed** | Prepare reproducible local environment | Version decisions, host details | Documented environment and path configuration | 0 | Validate Python/EnergyPlus discovery | Prerequisites are verified and documented |
| 2 | Baseline EnergyPlus building — **Completed** | Establish baseline office model | Original IDF, weather | Preserved source and runnable derived setup | 1 | Real baseline run | Model runs with declared inputs |
| 3 | Python EnergyPlus runner — **Completed** | Launch and coordinate simulation | Environment, model | Minimal runner interface | 1, 2 | Executed runner check | Runner starts simulation reproducibly |
| 4 | Live sensor extraction — **Completed** | Read declared state | Running simulation, sensor map | Timestamped structured observations | 3 | Compare reads to output records | Required available sensors are captured |
| 5 | Actuator injection — **Completed** | Apply validated controls | Handles, safe action | Observed actuator effect | 3, 4 | Handle and response check | Primary actuator injection works safely |
| 6 | State bus and storage — Pending | Normalize and persist state | Observations, action records | State schema and SQLite records | 4, 5 | Schema and persistence checks | Replayable state/action records exist |
| 7 | Rule-based fallback controller — Pending | Provide LLM-independent control | State bus, policy limits | Deterministic proposed action | 6 | Boundary and outage tests | Valid fallback operates without LLM |
| 8 | Safety guard — Pending | Enforce control constraints | Proposed actions, state | Accept/reject decision and reason | 5–7 | Invalid-action rejection tests | Unsafe/structurally invalid actions are rejected |
| 9 | Comfort-debt ledger — Pending | Track fairness debt by zone | Occupancy, comfort observations | Per-zone debt ledger | 6, 8 | Ledger scenario tests | Debt affects safety/candidate logic |
| 10 | Zone-flexibility estimator — Pending | Estimate temporary zone flexibility | State, occupancy, comfort bounds | Zone scores and rationale | 6, 9 | Deterministic score tests | Scores are logged and bounded |
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
