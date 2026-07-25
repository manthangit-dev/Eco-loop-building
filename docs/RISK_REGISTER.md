# Risk Register

| Risk | Probability | Impact | Detection method | Mitigation | Fallback |
| --- | --- | --- | --- | --- | --- |
| Windows 10 incompatibility with EnergyPlus 26.1 | Medium | High | Install/run check in Module 1 | Prefer supported host and document compatibility | Use configured WSL/Linux platform |
| EnergyPlus version mismatch with IDF | Medium | High | Version and model validation run | Pin 26.1.0 and preserve originals | Use a compatible documented model copy |
| Missing actuator handles | Medium | High | Enumerate handles in Module 5 | Validate target names before control | Run fallback without unavailable actuator |
| Missing output-variable handles | Medium | High | Sensor discovery log | Make required/optional map explicit | Mark unavailable and use safe reduced state |
| PMV unavailable in initial model | High | Low | Output-variable discovery | Treat PMV as optional | Operate without PMV |
| CO2 unavailable in initial model | High | Low | Output-variable discovery | Treat CO2 as optional | Operate without CO2 |
| LLM timeout | Medium | Medium | Timeout metrics | Bound request time and prompt size | Deterministic fallback |
| Invalid LLM JSON | Medium | Medium | Schema validation | Pydantic structured validation | Reject and use fallback |
| Unsafe LLM values | Medium | High | Safety-guard logs | Range, rate, and fairness checks | Reject and use fallback |
| Control oscillation | Medium | High | Trend and action-delta monitoring | Hysteresis and rate limits | Hold safe set-point/fallback |
| Long simulation logs | Medium | Low | Log size monitoring | Rotation and selected telemetry | Archive or summarize logs |
| Excessive prompt size | Medium | Medium | Token/size measurements | Compact state summaries | Use minimal deterministic context |
| Slow local LLM inference | High | Medium | Cycle latency measurement | Select model after hardware check | Deterministic fallback |
| Insufficient RAM or GPU | Medium | Medium | Hardware inspection | Choose smaller compatible model | Run without LLM |
| Non-reproducible external APIs | Medium | High | Input provenance audit | Use local versioned CSV signals | Retain local fixture inputs |
| Baseline and controlled runs use different inputs | Medium | High | Manifest comparison | Lock shared input manifest | Invalidate and rerun comparison |
| Comfort savings trade-off | Medium | High | Occupied comfort metrics | Debt ledger and guard constraints | Prioritize comfort-first fallback |
| Generated result files accidentally committed | Medium | Medium | Git status/review | `.gitignore` and output separation | Remove from index; retain local copy |
| Codex implements modules out of sequence | Medium | Medium | Module-plan review | Persistent AGENTS.md rules | Stop, revert scoped changes safely |
| Python 3.12 launcher is unavailable or inaccessible | High | High | `py -3.12 --version` and environment checker | Install or repair Python 3.12 and recreate `.venv` | Use a supported WSL Python 3.12 environment |
| `ENERGYPLUS_HOME` is unset or invalid | High | High | Module 1 environment checker | Configure local `.env` with the real installation directory | Install and verify EnergyPlus 26.1.0 on the selected platform |
| Source header names Chicago TMY2 while Module 2 requires Chicago O'Hare TMY3 | Medium | Medium | Compare IDF header, configured EPW filename, and manifest checksum | Record exact TMY3 provenance with every baseline result | Reject comparisons that do not use the manifest weather checksum |
| Baseline EnergyPlus warnings obscure validity | Low | High | Parse the authoritative final ERR summary | Require zero severe/fatal errors and report every warning | Keep Module 2 incomplete until reviewed; verified run produced zero warnings |
