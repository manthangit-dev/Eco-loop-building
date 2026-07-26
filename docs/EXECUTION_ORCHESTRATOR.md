# Execution Orchestrator

Module 15 can display persisted execution evidence but cannot approve, arm, execute, write,
or reset anything.

Module 14A adds schema-2 exact source/forecast, RunPeriod, derived-IDF, weather, and timestep binding.

Module 14 is simulation-only. It executes only the persisted Module 13 COMFORT_FIRST plan after exact preflight and local approval binding. The default `REPLAY_DRY_RUN` mode starts no EnergyPlus process and performs no actuator call. `LIVE_SHADOW` evaluates live committed states without writing. `LIVE_SHORT_HORIZON` requires a separate explicit approval and is restricted to the canonical `SPACE3-1` cooling-setpoint actuator in °C. `FAULT_INJECTION_FAKE_WRITER` supports deterministic failure testing.

The trusted chain is: persisted action → live state → `ProposedCommand` → Module 8 `SafetyGuard` → unforgeable `GuardedCommand` → existing physical write gate. No second writer or safety implementation exists. The LLM, MCP, planner, MicroTwin, ledger, approval parser, and dashboard have no physical authority.

The explicit state machine is IDLE → PREFLIGHT → APPROVAL_REQUIRED → ARMED → WAITING_FOR_LIVE_STATE → EXECUTING/HOLDING → RESETTING_TO_NATIVE → COMPLETED. Integrity failures enter FALLBACK_ACTIVE and then reset/abort. Invalid transitions fail closed. The scheduler binds action identity, order, relative offset, timing window, requested value, limits, exactly-once completion, hold, and mandatory restoration.

The live integration used 12 weather-run-period zone timesteps. Module 8 returned `ALLOW` for the single 28.5 °C action and `RESET_TO_NATIVE` at shutdown. The existing physical gate recorded one set, one reset, and zero writes without guard decisions. No annual run or real hardware control occurred.

Tested commands:

```powershell
.\.venv\Scripts\python.exe scripts\preflight_module_14.py
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\verify_module_14_fast.ps1
.\.venv\Scripts\python.exe scripts\run_execution_short.py --mode native --output outputs\module14\short_native.json
.\.venv\Scripts\python.exe scripts\run_execution_short.py --mode shadow --approval outputs\module14\shadow_approval.json --output outputs\module14\short_shadow.json
.\.venv\Scripts\python.exe scripts\run_execution_short.py --mode live --approval outputs\module14\live_approval.json --output outputs\module14\short_live.json
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\verify_module_14_full.ps1 -ReusePassingPytest
```

Module 15 dashboard work is not implemented.
