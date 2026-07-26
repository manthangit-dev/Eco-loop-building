[CmdletBinding()]
param()
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Root ".venv\Scripts\python.exe"
$Started = Get-Date
Set-Location $Root
& $Python scripts/validate_microtwin_replay_manifest.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $Python scripts/validate_microtwin.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $Python scripts/validate_module_12_closure.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $Python -B -m pytest -p no:cacheprovider
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $Python -m ruff check .
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $Python -m mypy --strict src scripts tests
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Output ("MODULE 12B CLOSURE VERIFICATION: PASS ({0}s; EnergyPlus, retraining, and Ollama skipped)" -f [math]::Round(((Get-Date)-$Started).TotalSeconds,3))
