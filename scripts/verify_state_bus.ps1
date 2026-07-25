$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
    throw "Repository virtual-environment Python is missing: $Python"
}
Set-Location $ProjectRoot

function Invoke-Checked {
    param(
        [Parameter(Mandatory = $true)][string]$Label,
        [Parameter(Mandatory = $true)][scriptblock]$Command
    )
    & $Command
    if ($LASTEXITCODE -ne 0) {
        throw "$Label failed with exit code $LASTEXITCODE."
    }
    Write-Host "PASS: $Label"
}

Invoke-Checked "Python version" { & $Python --version }
Invoke-Checked "SQLite version" {
    & $Python -c "import sqlite3; print(sqlite3.sqlite_version)"
}
Invoke-Checked "Environment" { & $Python scripts/check_environment.py }
Invoke-Checked "Configuration syntax" {
    $ConfigCode = @'
import json
from pathlib import Path
import yaml
for name in ('project', 'baseline', 'api_runner', 'sensors', 'actuators', 'state_bus'):
    yaml.safe_load(Path(f'config/{name}.yaml').read_text(encoding='utf-8'))
for name in ('config/zone_classification.json', 'models/MODEL_MANIFEST.json'):
    json.loads(Path(name).read_text(encoding='utf-8'))
print('Configuration files parsed.')
'@
    & $Python -c $ConfigCode
}
Invoke-Checked "Tests" { & $Python -B -m pytest -p no:cacheprovider }
Invoke-Checked "Ruff" { & $Python -m ruff check . --no-cache }
Invoke-Checked "Mypy" {
    & $Python -m mypy --no-incremental src scripts tests
}
Invoke-Checked "Replay database" {
    & $Python scripts/validate_state_storage.py --state-config config/state_bus.yaml --mode replay
}
Invoke-Checked "Live database" {
    & $Python scripts/validate_state_storage.py --state-config config/state_bus.yaml --mode live
}
Invoke-Checked "Replay inspection" {
    & $Python scripts/inspect_state_database.py --state-config config/state_bus.yaml `
        --mode replay --recent 1 | Out-Null
}
Invoke-Checked "Live inspection" {
    & $Python scripts/inspect_state_database.py --state-config config/state_bus.yaml `
        --mode live --recent 1 --zone-id space1_1 | Out-Null
}

$Forbidden = & rg -n `
    "get_actuator_handle|set_actuator_value|reset_actuator|control_decision" `
    src/state src/storage scripts/replay_sensor_states.py `
    scripts/run_state_bus_integration.py
if ($LASTEXITCODE -gt 1) {
    throw "Actuator/control scan failed."
}
if ($Forbidden -match "get_actuator_handle|set_actuator_value|reset_actuator") {
    throw "Module 6 contains actuator API access."
}
Write-Host "PASS: No Module 6 actuator API access"
Write-Host "PASS: Module 6 state bus and storage verification succeeded."
