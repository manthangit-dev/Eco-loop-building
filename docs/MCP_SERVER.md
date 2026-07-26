# Module 9 Local MCP Server

Module 15 adds no tools: catalogue version 5 retains 44 tools and control stays disabled.

Catalogue version 3 registers 30 tools, including six Module 12 tools: `get_microtwin_status`, `get_microtwin_validation`, `evaluate_plan_with_microtwin`, `compare_microtwin_rollouts`, `get_microtwin_rollout`, and `rank_plans_with_microtwin`. No training tool is exposed and `propose_guarded_control` remains disabled.

Module 12A confirms exactly 30 current tools and a deterministic catalogue fingerprint. Current tests and scripts contain no stale 18/24-tool assertion; historical reports retain accurate historical counts.

Module 9 exposes a deterministic, local-only tool layer over recorded Modules 6–8 artifacts.
It uses the official Python MCP SDK 1.28.1 over stdio, opens no TCP listener, starts no
EnergyPlus process, and uses no LLM.

Run `.\.venv\Scripts\python.exe scripts\run_mcp_server.py`. The fixed catalogue contains
18 tools: 16 read-only tools, `validate_control_proposal` for no-write Module 8 validation,
and disabled `propose_guarded_control`. Dry runs never instantiate the actuator writer.

Pydantic requests and envelopes are schema-versioned, deterministically serialized,
bounded, and audited in an additive schema-v4 SQLite database. Identical request IDs and
payloads are idempotent; conflicting duplicates fail closed.

Run `.\scripts\verify_module_9_fast.ps1` or `.\scripts\verify_module_9_full.ps1`. Both
reuse recorded artifacts and do not run EnergyPlus. Evidence is generated below
`data/output/module_9_mcp/` and excluded from Git. Energy values are diagnostics, not
savings claims.

Limitations: only configured local runs are queryable; physical control is unavailable;
comfort results report evidence coverage, not improvement; and no LLM is implemented.

Stable manual commands are `scripts/list_mcp_tools.py`, `scripts/call_mcp_tool.py`, and
`scripts/run_mcp_server_smoke.py`. The current demo generates their request files from a
usable recorded run; see `docs/CURRENT_DEMO.md`.
# Module 11 planning tools

Catalogue version 2 contains 24 tools. Six advisory planning tools provide forecast
context, deterministic generation, candidate evaluation/comparison, session inspection,
and advisory selection. No plan-execution tool exists, and `propose_guarded_control`
remains disabled. Planning calls use local stdio and perform zero physical writes.
# Module 13 catalogue v4

Catalogue v4 contains 40 tools: 30 read-only, 9 proposal-only, and one disabled control-capable tool. Ten ledger tools expose status, entries, comparisons, evaluations, rankings, bank status/transactions, and advisory selection. There is no debt-forgiveness or direct balance-mutation tool. Catalogue fingerprint: `d443796b22f688e68e74404d3c118d2456d55bc33a2adf17f65b64ce3e462fbc`.

# Module 14 catalogue v5

Catalogue v5 contains 44 tools: 34 read-only, 9 proposal-only, and one disabled control-capable tool. `get_execution_approval_status`, `get_plan_execution_status`, `get_plan_execution_audit`, and `compare_execution_runs` provide bounded observability only. No execution-start/arm/approve tool exists, and `propose_guarded_control` remains disabled. Fingerprint: `b97af3b310e48b0014f9a00a34e83737d6798b7fcda58da957b98a985477dcd6`.
