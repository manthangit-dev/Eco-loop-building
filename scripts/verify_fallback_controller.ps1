$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
    throw "Repository Python is missing: $Python"
}
Set-Location $Root

function Invoke-Checked {
    param([string]$Label, [scriptblock]$Command)
    & $Command
    if ($LASTEXITCODE -ne 0) { throw "$Label failed with exit code $LASTEXITCODE." }
    Write-Host "PASS: $Label"
}

Invoke-Checked "Environment" { & $Python scripts/check_environment.py }
Invoke-Checked "Module 2 baseline" {
    & $Python scripts/validate_baseline.py --config config/baseline.yaml
}
Invoke-Checked "Module 3 comparison" {
    & $Python scripts/compare_runner_outputs.py --config config/api_runner.yaml
}
Invoke-Checked "Module 4 sensors" {
    & $Python scripts/validate_sensor_extraction.py --sensor-config config/sensors.yaml
}
Invoke-Checked "Module 4 comparison" {
    & $Python scripts/compare_sensor_run_to_baseline.py --api-config config/api_runner.yaml
}
Invoke-Checked "Module 5 actuator" {
    & $Python scripts/validate_actuator_test.py --actuator-config config/actuators.yaml `
        --run-type both
}
Invoke-Checked "Module 5 comparison" {
    & $Python scripts/compare_actuator_runs.py --actuator-config config/actuators.yaml
}
Invoke-Checked "Module 6 replay" {
    & $Python scripts/validate_state_storage.py --state-config config/state_bus.yaml --mode replay
}
Invoke-Checked "Module 6 live" {
    & $Python scripts/validate_state_storage.py --state-config config/state_bus.yaml --mode live
}
Invoke-Checked "Tests" { & $Python -B -m pytest -p no:cacheprovider }
Invoke-Checked "Ruff" { & $Python -m ruff check . --no-cache }
Invoke-Checked "Mypy" { & $Python -m mypy --no-incremental src scripts tests }
Invoke-Checked "Replay shadow one" {
    & $Python scripts/replay_fallback_controller.py --quiet `
        --output-directory data/output/module_7_fallback_controller/replay_shadow/run_1
}
Invoke-Checked "Replay shadow two" {
    & $Python scripts/replay_fallback_controller.py --quiet `
        --output-directory data/output/module_7_fallback_controller/replay_shadow/run_2
}
Invoke-Checked "Live shadow" {
    & $Python scripts/run_fallback_shadow.py --quiet
}
Invoke-Checked "Replay validation" {
    & $Python scripts/validate_fallback_controller.py --mode replay_shadow `
        --output-directory data/output/module_7_fallback_controller/replay_shadow/run_1
}
Invoke-Checked "Live shadow validation" {
    & $Python scripts/validate_fallback_controller.py --mode live_shadow
}
Invoke-Checked "Live control" {
    & $Python scripts/run_fallback_controller.py --quiet
}
Invoke-Checked "Live control validation" {
    & $Python scripts/validate_fallback_controller.py --mode live_control
}
Invoke-Checked "Run comparison" { & $Python scripts/compare_fallback_runs.py }

$Forbidden = & rg -n "ollama|requests\.|urllib|socket|mcp|comfort.debt|final_safety_guard_implemented: true" `
    src/control src/storage scripts config/fallback_controller.yaml `
    -g "controller_*.py" -g "*fallback*.py" -g "fallback_controller.yaml"
if ($LASTEXITCODE -gt 1) { throw "Forbidden-feature scan failed." }
if ($Forbidden) { throw "Forbidden Module 8/later or network feature found: $Forbidden" }
Write-Host "PASS: No LLM, MCP, network, comfort debt, or Module 8 guard"
Write-Host "PASS: Module 7 deterministic fallback verification succeeded."
