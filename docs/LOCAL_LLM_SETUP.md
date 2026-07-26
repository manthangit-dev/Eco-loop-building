# Local LLM setup — Module 10B

Module 10 uses official Ollama 0.32.4 at `http://127.0.0.1:11434` and the local
`qwen3:0.6b` model (digest prefix `7df6b6e09427`, reported download 522 MB).
The 0.6B fallback was selected because the 7.34 GiB machine had only about
437 MiB available before installation. The machine has an AMD Ryzen 5 5600H,
12 logical processors, an RX 6500M, and about 172.2 GiB free on C:.

The runtime was installed for the user from the official `Ollama.Ollama`
winget package. No account, cloud model, remote binding, firewall change, or
cloud fallback is used. Exactly one model was downloaded.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\setup_local_llm.ps1 -CheckOnly
.\.venv\Scripts\python.exe .\scripts\check_llm_provider.py
.\.venv\Scripts\python.exe .\scripts\test_ollama_tool_call.py --pretty
.\.venv\Scripts\python.exe .\scripts\run_llm_real_smoke.py --pretty
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_current_demo.ps1 -TryRealModel
```

The native tool-call test passed without JSON fallback. Four real sessions used
`get_building_state`, `get_safety_guard_status`, and
`validate_control_proposal`; the forbidden `propose_guarded_control` request was
blocked by fixed policy and persisted as a policy event. The dry-run rerun
reached Module 8 and returned `REJECT_NO_WRITE / command_from_future`.

Physical-write counters did not change from 51,539 total records. New set calls,
resets, unguarded writes, forbidden-tool executions, and EnergyPlus processes
were all zero. See `outputs/module10b/zero_write_comparison.json` and
`data/output/module_10_llm/real_model_smoke.json`.

The default current demo remains mock-based. `-TryRealModel` only checks and
uses an already-installed runtime/model; it never installs or downloads one.
To stop Ollama, exit its tray application or run `Stop-Process -Name ollama`
when no local generation is active. If the endpoint is unavailable, start the
Ollama application and rerun `check_llm_provider.py`.

Known limitation: the 0.6B model can produce weak or contradictory prose. Tool
selection, typed arguments, evidence, safety outcomes, and writes remain under
deterministic validation; model prose is never authority for control. Module 11
has not begun.
