# Module 10A Runtime Command Audit

Audit date: 2026-07-26. Commands were inspected, invoked with `--help` where applicable,
then executed from the repository root using `.venv\Scripts\python.exe`. Detailed demo
logs are stored under `outputs\demo\logs`. The original command set had missing wrappers,
positional-only arguments, missing help parsers, current-directory assumptions, and
unhandled SDK stderr/plain-text errors.

| Advertised command / area | Actual path | Exists originally | Original result / cause | Correction and requirements | Final tested command | Exit | Status |
|---|---|---:|---|---|---|---:|---|
| Python / imports | `.venv\Scripts\python.exe` | Yes | Worked | Root `.venv`; imports mcp/pydantic/yaml | `.\.venv\Scripts\python.exe -c "import mcp,pydantic,yaml"` | 0 | PASS |
| Project/config | `config/*.yaml` | Yes | Worked | Root-derived loaders | demo steps 1–3 | 0 | PASS |
| Module 10 fast | `verify_module_10_fast.ps1` | Yes | Worked with Bypass | No EnergyPlus | `powershell.exe -ExecutionPolicy Bypass -File scripts\verify_module_10_fast.ps1` | 0 | PASS |
| Module 10 full | `verify_module_10_full.ps1` | Yes | Worked with Bypass | No EnergyPlus | same interface | 0 | PASS |
| Module 9 closure | `verify_module_9_closure.py` | Yes | Worked | Closure replay required | documented command | 0 | PASS |
| LLM validation | `validate_llm_supervisor.py` | Yes | `--help` executed validation | Added argparse help | `.\.venv\Scripts\python.exe scripts\validate_llm_supervisor.py` | 0 | PASS |
| List MCP tools | `list_mcp_tools.py` | No | Missing script | Canonical config; no DB required | `.\.venv\Scripts\python.exe scripts\list_mcp_tools.py` | 0 | REPAIRED |
| List tools JSON/filter | same | No | Missing | Added JSON, enabled, classification filters | `... list_mcp_tools.py --json` | 0 | REPAIRED |
| Select run | `select_demo_run.py` | No | Missing/stale IDs | Requires recorded state/controller/safety DBs | `.\.venv\Scripts\python.exe scripts\select_demo_run.py` | 0 | REPAIRED |
| Generate requests | `prepare_demo_requests.py` | No | Missing/manual JSON edits | Uses selected run/state/environment | `.\.venv\Scripts\python.exe scripts\prepare_demo_requests.py` | 0 | REPAIRED |
| Call MCP tool | `call_mcp_tool.py` | No | Missing | Starts real stdio server; JSON input | `... --tool get_building_state --input-file outputs\demo\requests\get_building_state.json` | 0 | REPAIRED |
| List available runs | same | No | No stable CLI | Generated input | demo step 8 | 0 | REPAIRED |
| Metadata/building/zone | same | No | No stable CLI | Dynamic request files | demo step 8 | 0 | REPAIRED |
| Safety/write audit | same | No | No stable CLI | Dynamic request files | demo step 8 | 0 | REPAIRED |
| MCP replay | `replay_mcp_session.py` | Yes | Worked with required output | Recorded DB | closure verifier | 0 | PASS |
| MCP smoke | `smoke_mcp_server.py` | Yes | No `--help`; SDK stderr upset PS5 | Added quiet wrapper | `.\.venv\Scripts\python.exe scripts\run_mcp_server_smoke.py` | 0 | REPAIRED |
| Mock supervisor | `run_llm_supervisor.py` | Yes | Positional file only | Added `--input-file`, `--pretty`, errors | documented mock command | 0 | REPAIRED |
| Controller objective | same | Yes | Wrong tool selection | Objective-aware mock selection | generated objective / same CLI | 0 | REPAIRED |
| Mock suite | `run_llm_mock_replay.py` | Yes | Required `--output` | Added safe default and failure details | `.\.venv\Scripts\python.exe scripts\run_llm_mock_replay.py` | 0 | REPAIRED |
| Valid proposal | `run_demo_control_proposal.py` | No | Missing | Dynamic guard config/run; dry-run only | `... --case valid` | 0 | REPAIRED |
| Rejected proposal | same | No | Missing | Canonical PLENUM-1 rejection | `... --case plenum` | 0 | REPAIRED |
| MCP audit | `inspect_mcp_audit.py` | Yes | Aggregate-only; list crash | Added latest/JSON/run and bounded detail | `... --latest --json` | 0 | REPAIRED |
| LLM audit | `inspect_llm_sessions.py` | Yes | No CLI/help | Added latest/JSON/session/run filters | `... --latest --json` | 0 | REPAIRED |
| Model discovery | `discover_local_models.py` | Yes | No help; runtime missing | Added help; missing runtime is structured | documented command | 0 | REPAIRED |
| Provider check | `check_llm_provider.py` | Yes | No help | Added help; local unhealthy reported | documented command | 0 | REPAIRED |
| Real smoke | `run_llm_real_smoke.py` | Yes | No help; skipped model | Added help; structured skip retained | documented command | 0 | REPAIRED |
| Optional setup | `setup_local_llm.ps1` | No | Missing | Check-only default; explicit installs | `powershell.exe ... setup_local_llm.ps1 -CheckOnly` | 0 | REPAIRED |
| One-command demo | `run_current_demo.ps1` | No | Missing | 12 fail-propagating logged steps | `powershell.exe ... run_current_demo.ps1` | 0 | REPAIRED |

All user-facing Python scripts in the repaired inventory return help exit 0. The current
machine's PowerShell policy blocks direct unsigned `.ps1` execution, so the fully tested
portable command uses process-scoped `-ExecutionPolicy Bypass`. No environment variable,
absolute user path, Ollama runtime, EnergyPlus process, or physical writer is required.
