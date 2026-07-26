# Hackathon demonstration script

## Five-minute flow

1. Open Overview: “ThermoLedger AI turns EnergyPlus state into deterministic candidates;
   the LLM is advisory and Module 8 remains the physical authority.”
2. Show candidates and MicroTwin: “The qualified thermal surrogate compares bounded
   trajectories; the demand model is unavailable.”
3. Show Ledger and Bank: “These are fairness and relative-flexibility proxies. RTFU is not
   energy.”
4. Show approval and safety: “The exact simulation package was locally approved, every set
   and reset was guarded, and native control was restored.”
5. Show native/live and reconciliation: “The zone cooled by up to about 1.203°C, while
   electricity increased. This three-hour result is not annual savings. Coverage was
   41.67%, so MicroTwin applicability is degraded but usable.”
6. End at provenance and limitations.

## Ten-minute flow

Use the five-minute flow, then inspect all candidate rankings, rollout uncertainty,
Comfort Equity proxies, zero Thermal Bank transactions, approval fingerprints, the guard
timeline, all twelve aligned points, and individual provenance records.

## Reviewer questions

- “Did it save energy?” — No established savings result; electricity increased in this
  short comfort-focused experiment.
- “Does it control a real building?” — No. It controls only a bounded simulation.
- “Does the LLM control HVAC?” — No. It is advisory; Module 8 gates the existing writer.
- “Is RTFU kWh?” — No. It is a relative accounting proxy.
- “Why is interval coverage low?” — Live-context coverage was 41.67%; the result is shown
  as degraded but usable, without retraining or hiding the limitation.

Avoid claims of annual savings, real-building performance, guaranteed comfort, physical
thermal storage, or whole-HVAC demand attribution.

Tested commands:

```powershell
.\.venv\Scripts\python.exe scripts/validate_dashboard_evidence.py --pretty
.\.venv\Scripts\python.exe scripts/check_evidence_dashboard.py --url http://127.0.0.1:8765 --pretty
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_hackathon_demo.ps1
```

If the browser does not open, manually visit `http://127.0.0.1:8765/` after running the
command. No internet, EnergyPlus process, or Ollama process is required.
