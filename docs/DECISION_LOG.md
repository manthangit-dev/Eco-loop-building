# Decision Log

| ID | Date | Decision | Reason | Alternatives rejected | Revisit condition |
| --- | --- | --- | --- | --- | --- |
| D-001 | 2026-07-25 | Use EnergyPlus 26.1.0 | Frozen MVP target | Unpinned/latest version | Compatibility issue with chosen model/platform |
| D-002 | 2026-07-25 | Use Python 3.12 | Frozen MVP target | Other Python versions | Dependency compatibility requires change |
| D-003 | 2026-07-25 | Start with a five-zone office | Manageable fairness scenario | Single zone or complex building | Model cannot support required controls |
| D-004 | 2026-07-25 | Use 15-minute control intervals | Balances responsiveness and stability | Shorter or longer intervals | Real experiments show instability or missed peaks |
| D-005 | 2026-07-25 | Cooling set-point is primary actuator | Clear initial control surface | Other HVAC actuators | Actuator unavailable or ineffective |
| D-006 | 2026-07-25 | Ventilation multiplier is secondary | Secondary flexibility option | Wider actuator set | Model/handles do not support it |
| D-007 | 2026-07-25 | Use local CSV external signals | Reproducibility | Live external APIs | Better reproducible approved source is available |
| D-008 | 2026-07-25 | Run baseline and AI sequentially | Identical-input comparison is simpler | Dual live instances | Stretch goal becomes necessary and validated |
| D-009 | 2026-07-25 | Use Streamlit dashboard | Fast prototype visualization | Other dashboard frameworks | UX needs exceed Streamlit scope |
| D-010 | 2026-07-25 | Use SQLite storage | Local, simple, reproducible storage | Remote database | Scale or concurrency requires change |
| D-011 | 2026-07-25 | Use Ollama runtime | Local open-source LLM route | Hosted LLM service | Hardware/runtime makes it unsuitable |
| D-012 | 2026-07-25 | Postpone exact LLM model | Hardware is unknown | Premature model selection | Hardware inspection completes |
| D-013 | 2026-07-25 | Separate LLM proposals from deterministic safety | Prevent direct unsafe actuation | Direct LLM control | Never for MVP safety boundary |
| D-014 | 2026-07-25 | PMV and CO2 are optional pending verification | Initial model may not expose them | Treating them as required | Model capability is verified |
| D-015 | 2026-07-25 | Use native Windows for the current Module 1 verification attempt | The current runtime reports Windows; no WSL kernel marker is present | Assuming WSL or Linux without evidence | Verification moves to a different host/runtime |
| D-016 | 2026-07-25 | Preserve the EnergyPlus 26.1 five-zone example and add only SQLite reporting to the derived baseline | Both the byte-identical source smoke run and reporting-only baseline completed against the official Chicago O'Hare TMY3 file with zero warnings, severe errors, or fatal errors | Editing physical inputs or adding unverified outputs | A later approved module requires a separately derived model |
