$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Root ".venv\Scripts\python.exe"
$Started = Get-Date
function Assert-NativeSuccess { if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE } }
Set-Location $Root
& $Python scripts/replay_mcp_session.py --output data/output/module_9_mcp/replay/closure_fast.json
Assert-NativeSuccess
& $Python scripts/verify_module_9_closure.py --replay data/output/module_9_mcp/replay/closure_fast.json
Assert-NativeSuccess
& $Python -m pytest -q tests/test_mcp_models.py tests/test_mcp_service.py tests/test_llm_config.py tests/test_llm_provider.py tests/test_agent_policy_parser.py tests/test_agent_context.py tests/test_agent_supervisor.py tests/test_llm_storage.py tests/test_llm_scenarios.py
Assert-NativeSuccess
& $Python -m ruff check src/llm src/agent src/mcp_server src/storage/llm_schema.py src/storage/llm_store.py scripts/*llm*.py scripts/verify_module_9_closure.py tests/test_llm_*.py tests/test_agent_*.py
Assert-NativeSuccess
& $Python -m mypy --no-incremental src/llm src/agent src/storage/llm_schema.py src/storage/llm_store.py scripts/discover_local_models.py scripts/check_llm_provider.py scripts/run_llm_mock_replay.py scripts/compare_llm_mock_replays.py scripts/run_llm_real_smoke.py scripts/run_llm_supervisor.py scripts/inspect_llm_sessions.py scripts/validate_llm_supervisor.py
Assert-NativeSuccess
& $Python scripts/run_llm_mock_replay.py --output data/output/module_10_llm/mock/mock_1.json
Assert-NativeSuccess
& $Python scripts/run_llm_supervisor.py examples/llm/describe_current_state.json --provider mock
Assert-NativeSuccess
& $Python scripts/validate_llm_supervisor.py
Assert-NativeSuccess
$Elapsed = [math]::Round(((Get-Date) - $Started).TotalSeconds, 3)
Write-Output "MODULE 10 FAST VERIFICATION: PASS (${Elapsed}s)"
