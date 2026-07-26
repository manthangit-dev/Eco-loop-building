[CmdletBinding()]
param([switch]$SkipRealSmoke)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Root ".venv\Scripts\python.exe"
Set-Location $Root
& $Python -c "from pathlib import Path; from src.llm.config import load_llm_settings; s=load_llm_settings(Path('config/llm_supervisor.yaml')); assert s.endpoint=='http://127.0.0.1:11434' and s.local_only and s.dry_run_only and 'propose_guarded_control' in s.denied_tools"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $Python scripts/discover_local_models.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $Python scripts/check_llm_provider.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $Python scripts/test_ollama_tool_call.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
if (-not $SkipRealSmoke) { & $Python scripts/run_llm_real_smoke.py; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE } }
& $Python -m pytest tests/test_llm_config.py tests/test_llm_provider.py tests/test_agent_supervisor.py -q
exit $LASTEXITCODE

