# Acceptance Criteria

Modules 0 and 1 are complete. The real Module 1 checker passed on native Windows with Python
3.12 and EnergyPlus 26.1.0. All later criteria remain future work.

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

- At least 10% energy reduction, at least 10% peak-demand reduction, at least 95% occupied comfort compliance, and at least 98% successful control cycles.
- These are targets only. They must be measured from real comparable simulations before being reported as achieved.

## Stretch goals

- Simultaneous baseline/AI instances, PMV and CO2 support where the model exposes them, and broader actuator coverage.
