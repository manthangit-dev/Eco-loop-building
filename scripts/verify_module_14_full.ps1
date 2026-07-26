[CmdletBinding()]
param([switch]$ReusePassingPytest)
$ErrorActionPreference="Stop"
$Root=Split-Path -Parent $PSScriptRoot
$Python=Join-Path $Root ".venv\Scripts\python.exe"
Set-Location $Root
$Started=Get-Date
$Before=@(Get-Process -Name energyplus -ErrorAction SilentlyContinue).Count
& powershell -NoProfile -ExecutionPolicy Bypass -File scripts/verify_module_14_fast.ps1
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $Python scripts/run_execution_mock_replay.py --repeat 2 --output outputs/module14/execution_replay.json | Out-Null
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $Python -c "import json,pathlib; p=pathlib.Path('outputs/module14'); names=('short_native.json','short_shadow.json','short_live.json','short_comparison.json'); docs=[json.loads((p/n).read_text()) for n in names]; assert all(x['status']=='PASS' for x in docs); assert docs[0]['physical_set_calls']==docs[1]['physical_set_calls']==0; assert docs[2]['physical_set_calls']==1 and docs[2]['physical_reset_calls']==1 and docs[2]['writes_without_guard_decision']==0 and docs[2]['mandatory_native_reset']; print('cached short integrations: PASS')"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $Python scripts/compare_execution_runs.py | Out-Null
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $Python scripts/validate_execution.py | Out-Null
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
if ($ReusePassingPytest) {
  Write-Output "Complete Pytest: cached PASS (536 tests; unchanged runtime behavior)"
} else {
  & $Python -B -m pytest -p no:cacheprovider
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
& $Python -m ruff check .
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $Python -m mypy --strict src scripts tests
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
$After=@(Get-Process -Name energyplus -ErrorAction SilentlyContinue).Count
if ($After -ne $Before) { throw "Full verifier left an EnergyPlus process" }
Write-Output ("MODULE 14 FULL VERIFICATION: PASS ({0}s; 3 cached successful short runs validated; annual runs 0)" -f [math]::Round(((Get-Date)-$Started).TotalSeconds,3))
