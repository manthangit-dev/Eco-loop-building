$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Root ".venv\Scripts\python.exe"
$Started = Get-Date
function Assert-NativeSuccess { if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE } }
Set-Location $Root
& $Python -B -m pytest -p no:cacheprovider
Assert-NativeSuccess
& $Python -m ruff check . --no-cache
Assert-NativeSuccess
& $Python -m mypy --no-incremental src scripts tests
Assert-NativeSuccess
& $Python scripts/validate_baseline.py --config config/baseline.yaml
Assert-NativeSuccess
& $Python scripts/replay_mcp_session.py --output data/output/module_9_mcp/replay/closure_full.json
Assert-NativeSuccess
& $Python scripts/verify_module_9_closure.py --replay data/output/module_9_mcp/replay/closure_full.json
Assert-NativeSuccess
& $Python scripts/run_llm_mock_replay.py --output data/output/module_10_llm/mock/full_1.json
Assert-NativeSuccess
& $Python scripts/run_llm_mock_replay.py --output data/output/module_10_llm/mock/full_2.json
Assert-NativeSuccess
& $Python scripts/compare_llm_mock_replays.py data/output/module_10_llm/mock/full_1.json data/output/module_10_llm/mock/full_2.json
Assert-NativeSuccess
& $Python scripts/smoke_mcp_server.py
Assert-NativeSuccess
& $Python scripts/discover_local_models.py
Assert-NativeSuccess
& $Python scripts/run_llm_real_smoke.py
Assert-NativeSuccess
& $Python scripts/validate_llm_supervisor.py
Assert-NativeSuccess
$Elapsed = [math]::Round(((Get-Date) - $Started).TotalSeconds, 3)
Write-Output "MODULE 10 FULL VERIFICATION: PASS (${Elapsed}s; real model may be skipped)"
