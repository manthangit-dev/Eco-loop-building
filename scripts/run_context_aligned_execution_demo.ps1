[CmdletBinding()]
param(
    [switch]$RunAcceptedShortIntegrations,
    [string]$ApprovalFile,
    [switch]$CreateSimulationApproval,
    [switch]$Json,
    [switch]$VerboseOutput,
    [switch]$KeepArtifacts
)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Root ".venv\Scripts\python.exe"
Set-Location $Root
& $Python scripts/run_module14a_replay.py --output outputs/module14a/demo_replay.json
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $Python scripts/control_effect_preflight.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
if ($RunAcceptedShortIntegrations) {
    throw "Accepted runs already exist; regeneration requires a relevant code/runtime change."
}
Write-Output "REPLAY_DRY_RUN PASS: exact July 19 binding ready; zero physical writes."
