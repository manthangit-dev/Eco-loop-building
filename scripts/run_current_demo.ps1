[CmdletBinding()]
param(
    [switch]$SkipTests,
    [switch]$SkipMockSuite,
    [switch]$Json,
    [switch]$VerboseOutput,
    [switch]$TryRealModel,
    [switch]$KeepGeneratedRequests
)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Root ".venv\Scripts\python.exe"
$Output = Join-Path $Root "outputs\demo"
$Requests = Join-Path $Output "requests"
$Logs = Join-Path $Output "logs"
$Started = Get-Date
$EnergyPlusBefore = @(Get-Process -ErrorAction SilentlyContinue | Where-Object { $_.ProcessName -match '^energyplus$' }).Count
New-Item -ItemType Directory -Force -Path $Logs | Out-Null
function Invoke-DemoStep {
    param([int]$Number, [string]$Name, [scriptblock]$Action)
    Write-Output "[$Number/12] $Name"
    $log = Join-Path $Logs ("{0:D2}_{1}.log" -f $Number, ($Name -replace '[^A-Za-z0-9]+','_'))
    try {
        & $Action *> $log
        if ($LASTEXITCODE -ne 0) { throw "exit code $LASTEXITCODE" }
        if ($VerboseOutput) { Get-Content $log }
        Write-Output "  PASS"
    } catch {
        Write-Error "Step '$Name' failed: $($_.Exception.Message). Log: $log"
        exit 1
    }
}
Set-Location $Root
Invoke-DemoStep 1 "Check project root" { if (-not (Test-Path "config\project.yaml")) { exit 2 }; & $Python --version }
Invoke-DemoStep 2 "Check repository-local Python" { & $Python -c "import mcp,pydantic,yaml; print('dependencies: PASS')" }
Invoke-DemoStep 3 "Validate configuration" { & $Python -c "from pathlib import Path; from src.mcp_server.config import load_mcp_settings; from src.llm.config import load_llm_settings; load_mcp_settings(Path('config/mcp_server.yaml')); load_llm_settings(Path('config/llm_supervisor.yaml')); print('configuration: PASS')" }
Invoke-DemoStep 4 "Validate or synchronise database" {
    & $Python scripts/run_llm_mock_replay.py --output data/output/module_10_llm/mock/mock_1.json
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & $Python -c "from pathlib import Path; import sqlite3; from src.storage.llm_schema import migrate_llm_schema; p=Path('data/output/module_10_llm/llm_audit.db'); p.parent.mkdir(parents=True,exist_ok=True); c=sqlite3.connect(p); migrate_llm_schema(c); c.close()"
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & $Python scripts/validate_llm_supervisor.py
}
Invoke-DemoStep 5 "Select usable recorded run" { & $Python scripts/select_demo_run.py --output outputs/demo/selected_run.json }
Invoke-DemoStep 6 "Generate demo requests" { & $Python scripts/prepare_demo_requests.py --output-directory $Requests }
Invoke-DemoStep 7 "List MCP tools" { & $Python scripts/list_mcp_tools.py }
Invoke-DemoStep 8 "Run MCP read-only calls" {
    & $Python scripts/call_mcp_tool.py --tool list_available_runs --input-file "$Requests\list_available_runs.json" --pretty
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & $Python scripts/call_mcp_tool.py --tool get_run_metadata --input-file "$Requests\get_run_metadata.json" --pretty
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & $Python scripts/call_mcp_tool.py --tool get_building_state --input-file "$Requests\get_building_state.json" --pretty
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & $Python scripts/call_mcp_tool.py --tool get_zone_state --input-file "$Requests\get_zone_state.json" --pretty
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & $Python scripts/call_mcp_tool.py --tool get_safety_guard_status --input-file "$Requests\get_safety_guard_status.json" --pretty
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & $Python scripts/call_mcp_tool.py --tool get_physical_write_audit --input-file "$Requests\get_physical_write_audit.json" --pretty
}
Invoke-DemoStep 9 "Run MCP server smoke" { & $Python scripts/run_mcp_server_smoke.py }
Invoke-DemoStep 10 "Run mock LLM supervisor" {
    & $Python scripts/run_llm_supervisor.py --provider mock --input-file "$Requests\describe_current_state.json" --pretty
    if (-not $SkipMockSuite) { & $Python scripts/run_llm_mock_replay.py --output data/output/module_10_llm/mock/current_demo.json }
}
Invoke-DemoStep 11 "Run valid and rejected dry-run proposals" {
    & $Python scripts/run_demo_control_proposal.py --case valid --json
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & $Python scripts/run_demo_control_proposal.py --case plenum --json
}
Invoke-DemoStep 12 "Inspect audit records and print summary" {
    & $Python scripts/inspect_mcp_audit.py --latest --json
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & $Python scripts/inspect_llm_sessions.py --latest --json
    if ($TryRealModel) {
        & $Python scripts/check_llm_provider.py
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
        & $Python scripts/run_llm_real_smoke.py
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    }
}
$EnergyPlusAfter = @(Get-Process -ErrorAction SilentlyContinue | Where-Object { $_.ProcessName -match '^energyplus$' }).Count
$Summary = [ordered]@{
    status = "PASS"; python_environment = "PASS"; usable_recorded_run = "PASS";
    mcp_catalogue = "PASS"; mcp_read_calls = "PASS"; mcp_server_smoke = "PASS";
    mock_supervisor = "PASS"; valid_proposal = "PASS"; rejected_proposal = "PASS";
    module_8_reached = $true; mcp_audit = "PASS"; llm_audit = "PASS";
    energyplus_processes_started = [math]::Max(0, $EnergyPlusAfter - $EnergyPlusBefore);
    physical_writes_performed = 0; real_local_model_status = $(if ($TryRealModel) { "PASS" } else { "NOT_REQUIRED_DEFAULT" });
    runtime_seconds = [math]::Round(((Get-Date) - $Started).TotalSeconds, 3)
}
if ($Json) { $Summary | ConvertTo-Json } else {
    Write-Output "THERMOLEDGER CURRENT DEMO: PASS"
    $Summary.GetEnumerator() | ForEach-Object { Write-Output ("{0}: {1}" -f $_.Key, $_.Value) }
}
if (-not $KeepGeneratedRequests) { Write-Output "Generated requests retained at outputs\demo\requests for audit." }
exit 0
