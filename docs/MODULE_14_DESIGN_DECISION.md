# Module 14 design decision

Module 14 introduces a simulation-only execution orchestrator. Authority is local and explicit: an immutable, expiring, one-time-use operator approval binds the exact persisted plan, rollout, ledger evaluation, model, canonical actuator, environment, and input checksums. The default mode is a zero-write replay dry run.

The physical chain remains singular: bound plan action → trusted live state → `ProposedCommand` → existing Module 8 `SafetyGuard` → unforgeable `GuardedCommand` → existing physical write gate. Planning, MicroTwin, ledger, MCP, and LLM components cannot write or create trusted timing. Module 7 fallback semantics and mandatory native reset remain deterministic and Module 8 protected.

Only a bounded 180-minute EnergyPlus simulation may be used for live validation. Results are scenario-specific short-horizon simulation differences, never annual or real-building savings.

