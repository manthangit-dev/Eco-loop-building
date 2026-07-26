[CmdletBinding()]
param()
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Root ".venv\Scripts\python.exe"
Set-Location $Root
$BeforeProcesses = @(Get-Process -Name energyplus -ErrorAction SilentlyContinue).Count
& $Python scripts/capture_module12c_zero_write.py --phase before --energyplus-process-count $BeforeProcesses | Out-Null
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

# Coverage acceptance is deliberately first; no PASS can be printed before it.
& $Python scripts/run_microtwin_mock_replay.py --validate-manifest --require-zero-coverage-gaps --require-dedicated-final-gaps --require-mutation-sensitivity --fail-on-category-only --fail-on-placeholder --audit-output outputs/module12c/final_replay_fixture_audit.json --output outputs/module12c/strict_validation.json --json | Out-Null
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $Python scripts/validate_microtwin.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $Python scripts/validate_module_12_closure.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $Python scripts/run_microtwin_mock_replay.py --repeat 2 --require-zero-coverage-gaps --require-dedicated-final-gaps --require-mutation-sensitivity --fail-on-category-only --fail-on-placeholder --json --output outputs/module12c/final_replay.json | Out-Null
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $Python -B -m pytest -p no:cacheprovider
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $Python -m ruff check .
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $Python -m mypy --strict src scripts tests
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
$AfterProcesses = @(Get-Process -Name energyplus -ErrorAction SilentlyContinue).Count
& $Python scripts/capture_module12c_zero_write.py --phase after --energyplus-process-count $AfterProcesses | Out-Null
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Output "MODULE 12C FINAL VERIFICATION: PASS (EnergyPlus, training, and Ollama skipped)"
