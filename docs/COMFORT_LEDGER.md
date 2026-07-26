# Comfort Ledger

Module 15 displays persisted burden and fairness only as `ADVISORY_PROXY` evidence.

Module 13 adds a deterministic, advisory-only Comfort Ledger for `SPACE3-1`. It evaluates the five qualified Module 12 MicroTwin rollouts without executing them. The ledger records relative thermal fairness units (RTFU), not energy, money, individual entitlements, or physical storage.

The demonstration boundaries are 22–26 °C, with a protected upper boundary of 25.5 °C. These values are explicit project assumptions in `config/comfort_ledger.yaml`; they are not inferred occupant preferences. Burden, credit, debt, consecutive burden, protected-event burden, event fairness, temporal fairness, and the Comfort Equity Score are computed deterministically. The LLM may explain stored results but cannot change them.

Opening credit and debt are zero for the Module 13 demonstration. Debt cannot be forgiven through MCP. Evaluations are persisted additively in schema 8, and all writes are application records only—never actuator writes. No occupant identity, personal information, or health data is collected.

Run `python scripts/evaluate_comfort_ledger.py` to reproduce the evaluation and `python scripts/inspect_comfort_ledger.py` to inspect persisted state.

Module 14 consumes only the persisted eligible selection. The ledger cannot approve, arm, time, modify, or execute an action. Its values are rechecked during exact preflight, while Module 8 remains the live safety authority.
