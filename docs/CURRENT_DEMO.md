# ThermoLedger Current Runtime Demo

The final evidence-only demo is `scripts/run_hackathon_demo.ps1`; it starts no simulation or LLM.

The Module 12 offline demo is `powershell -File scripts/run_microtwin_demo.ps1`. It reuses cached annual telemetry and trained artifacts, evaluates all eligible plans, reports ranking disagreement, and confirms zero EnergyPlus starts and physical writes.

Closure evidence is validated with `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/verify_module_12_closure.ps1`. It does not start EnergyPlus or retrain the MicroTwin.

## One command

Prerequisites are the repository checkout and its existing `.venv`. From the repository
root, run:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_current_demo.ps1
```

If local execution policy already permits scripts, `.\scripts\run_current_demo.ps1` is
equivalent. The tested default demo selects recorded data dynamically, requires no Ollama,
starts no EnergyPlus process, and performs no physical writes. Success ends with
`THERMOLEDGER CURRENT DEMO: PASS` and exit code 0; a required-step failure returns nonzero
and writes details below `outputs\demo\logs\`.

The tested run selected `module8-live-control`, environment `weather-3`, latest state
35040, historical state 1, and confirmed SPACE3-1 plus observable PLENUM-1. Selection is
repeated on every run and these values are not hardcoded into requests.

## Individually tested commands

```powershell
.\.venv\Scripts\python.exe .\scripts\select_demo_run.py
.\.venv\Scripts\python.exe .\scripts\prepare_demo_requests.py
.\.venv\Scripts\python.exe .\scripts\list_mcp_tools.py
.\.venv\Scripts\python.exe .\scripts\list_mcp_tools.py --json
.\.venv\Scripts\python.exe .\scripts\call_mcp_tool.py --tool get_building_state --input-file .\outputs\demo\requests\get_building_state.json --pretty
.\.venv\Scripts\python.exe .\scripts\call_mcp_tool.py --tool get_safety_guard_status --input-file .\outputs\demo\requests\get_safety_guard_status.json --pretty
.\.venv\Scripts\python.exe .\scripts\run_mcp_server_smoke.py
.\.venv\Scripts\python.exe .\scripts\run_llm_supervisor.py --provider mock --input-file .\outputs\demo\requests\describe_current_state.json --pretty
.\.venv\Scripts\python.exe .\scripts\run_llm_mock_replay.py
.\.venv\Scripts\python.exe .\scripts\run_demo_control_proposal.py --case valid
.\.venv\Scripts\python.exe .\scripts\run_demo_control_proposal.py --case plenum
.\.venv\Scripts\python.exe .\scripts\inspect_mcp_audit.py --latest --json
.\.venv\Scripts\python.exe .\scripts\inspect_llm_sessions.py --latest --json
```

The valid proposal reached Module 8 with `ALLOW / allowed`. The PLENUM-1 proposal reached
Module 8 with `REJECT_NO_WRITE / plenum_zone_rejected`. These outcomes describe this
recorded demonstration only; both reported zero physical writes. The demo never invokes
`propose_guarded_control`.

## Optional local model

The default check is non-mutating:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\setup_local_llm.ps1 -CheckOnly
.\.venv\Scripts\python.exe .\scripts\run_llm_real_smoke.py
```

Ollama is currently missing, so smoke reports `SKIPPED_MISSING_LOCAL_MODEL`. Runtime
installation and model acquisition occur only with explicit `-InstallRuntime` and
`-InstallModel -Model <reviewed-name>` arguments. Module 10 remains incomplete until real
smoke passes.

## Common errors

- Execution-policy error: use the tested `powershell.exe ... -ExecutionPolicy Bypass`
  command above; this changes policy only for that process.
- Missing `.venv`: recreate the documented Python 3.12 environment before running.
- Missing database or no usable run: restore the generated Modules 7–9 recorded artifacts;
  `select_demo_run.py` prints every rejected run and reason.
- Missing dependency: run the repository dependency installation with the local interpreter.
- Missing Ollama: harmless for the default demo; required only for optional real smoke.
- Exit 0 means all required demo checks passed; exit 1 is a failed PowerShell step; Python
  CLIs generally use exit 2 for input/configuration failure and exit 3 for structured
  operation failure.
# Real-model option

Module 11 has a separate `scripts/run_planning_demo.ps1`. Its default is deterministic
and mock-based; `-TryRealModel` uses the already-verified local model artifact and never
installs software or downloads a model. The Module 10 current demo remains unchanged.

The default command remains mock-only and does not require Ollama. Adding
`-TryRealModel` runs the default demo first, checks the already-installed local
runtime/model, then runs the bounded recorded-data smoke. It never installs or
downloads a model and physical control remains disabled.
# Module 13 ledger demonstration

Run `powershell -ExecutionPolicy Bypass -File scripts/run_ledger_demo.ps1` for the deterministic/mock path, or add `-RealModel` to reuse or run the three-session local-model evidence workflow. The demo evaluates five candidates, persists schema-8 records, reports ranking differences, and asserts zero EnergyPlus-process and physical-write deltas. Results are advisory; they do not establish verified savings or comfort improvement.

# Module 14 demo

`powershell -NoProfile -ExecutionPolicy Bypass -File scripts/run_execution_demo.ps1` defaults to `REPLAY_DRY_RUN`, creates only a temporary dry-run approval, schedules the exact action through Module 8, performs zero writes, and confirms reset readiness. Live modes require an explicit approval file or the explicit simulation-approval option. The measured default demo passed in 3.882 s.
