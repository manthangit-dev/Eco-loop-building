# Architecture

## Implemented execution path through Module 3

```mermaid
flowchart TD
  BM[Verified EnergyPlus baseline model] --> AL[Python API loader]
  AL --> RR[Runtime API runner]
  RR --> CB[Lifecycle, progress, and bounded message callbacks]
  CB --> OUT[Run metadata and EnergyPlus outputs]
  OUT --> VAL[Existing baseline validator]
```

This implemented path starts the unchanged baseline and observes execution lifecycle only. It
does not yet read EnergyPlus variables, obtain actuator handles, control equipment, or invoke
AI.

## System architecture

```mermaid
flowchart LR
  EP[EnergyPlus digital twin] --> SB[Structured state bus]
  SB --> FE[Flexibility estimator]
  SB --> CDL[Comfort-debt ledger]
  SB --> MCP[MCP tool layer]
  MCP --> LLM[Ollama LLM planner]
  LLM --> CE[Candidate evaluator]
  FE --> CE
  CDL --> CE
  CE --> SG[Deterministic safety guard]
  SG -->|validated action| EP
  SG -->|reject or timeout| FB[Deterministic fallback]
  FB --> EP
  EP --> OBS[Outcome observation]
  OBS --> CR[Critic and self-correction]
  OBS --> ST[(SQLite and CSV/JSON)]
  ST --> DB[Streamlit dashboard]
```

## Closed-loop sequence

```mermaid
sequenceDiagram
  participant E as EnergyPlus
  participant S as State bus
  participant L as LLM planner
  participant G as Safety guard
  participant F as Fallback
  E->>S: Publish 15-minute state
  S->>L: Provide structured context and tools
  L->>G: Propose candidate action
  G->>G: Validate limits, fairness, and structure
  alt Valid
    G->>E: Inject validated action
  else Invalid or LLM failure
    G->>F: Request deterministic action
    F->>E: Inject safe fallback action
  end
  E->>S: Publish outcome
  S->>S: Store observations and critic feedback
```

## Components and responsibilities

The EnergyPlus layer owns model execution, sensor reads, and actuator injection. The state bus normalizes observations. The controller layer coordinates the comfort-debt ledger, flexibility estimator, thermal-battery strategy, and candidate evaluator. The ledger tracks fairness over time; the estimator measures temporary zone flexibility; the evaluator compares strategy candidates.

The MCP tool layer exposes structured, bounded tools to the LLM planner. The critic reviews outcomes but does not bypass safety. SQLite and CSV/JSON store reproducible observations and exports; Streamlit will visualize them. Error and timeout handling rejects malformed or late proposals, logs the reason, and invokes deterministic fallback.

The LLM proposes actions. Deterministic code validates actions. Only validated actions may reach EnergyPlus. The fallback controller must work without the LLM.

## Evaluation architecture

Separate baseline and AI runs consume identical inputs and periods. Their stored outputs are compared afterward for energy, peak demand, comfort, reliability, and fairness; no simultaneous execution is required for the MVP.
# Implemented Module 4 read-only path

```text
EnergyPlus
    ↓
Data Exchange API
    ↓
Read-only sensor registry
    ↓
End-of-zone-timestep callback
    ↓
Timestamped sensor snapshot
    ↓
JSONL and CSV output
    ↓
Sensor validation
```

This Module 4 path remains observational; the separate bounded Module 5 test path
is shown below.

## Implemented Module 5 deterministic test path

```text
Live sensor state
       ↓
Deterministic test plan
       ↓
Approved single actuator
       ↓
Actuation callback
       ↓
set_actuator_value
       ↓
EnergyPlus physical response
       ↓
reset_actuator
       ↓
Normal EnergyPlus control resumes
       ↓
Sensor and event validation
```

This is a fixed actuator-functionality test. The Module 6 state bus and autonomous
control are not implemented.
