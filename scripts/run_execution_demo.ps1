[CmdletBinding()]
param(
  [ValidateSet("REPLAY_DRY_RUN","LIVE_SHADOW","LIVE_SHORT_HORIZON")][string]$Mode="REPLAY_DRY_RUN",
  [string]$ApprovalFile="",
  [switch]$CreateSimulationApproval,
  [switch]$TryRealModelExplanation,
  [switch]$Json,
  [switch]$VerboseOutput,
  [switch]$KeepArtifacts,
  [switch]$SkipTests
)
$ErrorActionPreference="Stop"
$Root=Split-Path -Parent $PSScriptRoot
$Python=Join-Path $Root ".venv\Scripts\python.exe"
Set-Location $Root
$Started=Get-Date
$Plan="3ae11d4aa482502d4e1ff741ef49f007a22eb4a1067236651956d0defa113dae"
if (-not $SkipTests) { & $Python -B -m pytest -q tests/test_execution.py; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE } }
& $Python scripts/preflight_module_14.py | Out-Null
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
if (-not $ApprovalFile) {
  if ($Mode -ne "REPLAY_DRY_RUN" -and -not $CreateSimulationApproval) { throw "Live modes require explicit approval" }
  $ApprovalFile="outputs/module14/demo_approval.json"
  & $Python scripts/create_execution_approval.py --plan-id $Plan --mode $Mode --expires-in-minutes 15 --maximum-writes 20 --maximum-resets 2 --simulation-only --confirm --output $ApprovalFile --json | Out-Null
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
if ($Mode -eq "REPLAY_DRY_RUN") {
  & $Python scripts/run_execution_replay_dry_run.py --approval $ApprovalFile --output outputs/module14/execution_demo.json | Out-Null
} elseif ($Mode -eq "LIVE_SHADOW") {
  & $Python scripts/run_execution_short.py --mode shadow --approval $ApprovalFile --output outputs/module14/execution_demo.json | Out-Null
} else {
  & $Python scripts/run_execution_short.py --mode live --approval $ApprovalFile --output outputs/module14/execution_demo.json | Out-Null
}
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
$Result=@{status="PASS";mode=$Mode;physical_scope="EnergyPlus simulation only";runtime_seconds=[math]::Round(((Get-Date)-$Started).TotalSeconds,3)}
if ($Json) { $Result|ConvertTo-Json } else { Write-Output "MODULE 14 EXECUTION DEMO: PASS ($Mode)" }
