[CmdletBinding()]
param(
    [switch]$TryRealModel,
    [switch]$Json,
    [switch]$VerboseOutput,
    [switch]$KeepArtifacts,
    [switch]$SkipTests,
    [switch]$ResetDemoLedger
)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Root ".venv\Scripts\python.exe"
Set-Location $Root
$Started = Get-Date
$BeforeProcesses = @(Get-Process -Name energyplus -ErrorAction SilentlyContinue).Count
$BeforeWrites = & $Python -c "import sqlite3;c=sqlite3.connect(r'data/output/module_8_safety_guard/live_control/current/safety_guard.db');print(c.execute('select count(*) from physical_write_attempts').fetchone()[0])"
& $Python scripts/preflight_module_13.py --energyplus-process-count $BeforeProcesses | Out-Null
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $Python scripts/evaluate_comfort_ledger.py --output outputs/ledger/evaluations.json | Out-Null
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $Python scripts/validate_ledger.py | Out-Null
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
if (-not $SkipTests) {
    & $Python -m pytest tests/test_ledger.py tests/test_ledger_replay_fixtures.py -q
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
$Smoke = "outputs/module13/mock_model_smoke.json"
if ($TryRealModel) {
    $Smoke = "outputs/module13/real_model_smoke.json"
    if (-not (Test-Path $Smoke)) {
        & $Python scripts/run_ledger_real_smoke.py --real --output $Smoke | Out-Null
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    }
} else {
    if (-not (Test-Path $Smoke)) {
        & $Python scripts/run_ledger_real_smoke.py --output $Smoke | Out-Null
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    }
}
$AfterProcesses = @(Get-Process -Name energyplus -ErrorAction SilentlyContinue).Count
$AfterWrites = & $Python -c "import sqlite3;c=sqlite3.connect(r'data/output/module_8_safety_guard/live_control/current/safety_guard.db');print(c.execute('select count(*) from physical_write_attempts').fetchone()[0])"
$Evaluation = Get-Content outputs/ledger/evaluations.json -Raw | ConvertFrom-Json
$Summary = [ordered]@{
    status = $(if (($AfterProcesses-$BeforeProcesses) -eq 0 -and ([int]$AfterWrites-[int]$BeforeWrites) -eq 0) { "PASS" } else { "FAIL" })
    selected_plan = $Evaluation.ranking.selected_plan_id
    rankings_all_agree = $Evaluation.ranking.rankings_all_agree
    evaluation_count = $Evaluation.evaluations.Count
    ledger_unit = "relative comfort proxy"
    thermal_bank_unit = "RTFU"
    physical_write_delta = ([int]$AfterWrites-[int]$BeforeWrites)
    energyplus_process_delta = ($AfterProcesses-$BeforeProcesses)
    real_model = $TryRealModel.IsPresent
    runtime_seconds = [math]::Round(((Get-Date)-$Started).TotalSeconds,3)
}
$Output = "outputs/module13/ledger_demo.json"
$Summary | ConvertTo-Json | Set-Content -Encoding UTF8 $Output
if ($Json) { $Summary | ConvertTo-Json } else { $Summary | Format-List | Out-String | Write-Output }
if ($Summary.status -ne "PASS") { exit 1 }
