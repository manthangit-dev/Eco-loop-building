# Module 14A validation repair

The preserved investigation measures the original 201-day (4,836-hour) mismatch and
classifies its reconciliation `INVALID_TEMPORAL_ALIGNMENT`. The repair adds exact-window
rejection, deterministic Path-B selection, a derived July 19 runtime, non-native preflight,
three compatible accepted runs, schema-10 evidence, and 80 replay scenarios with zero gaps.
Replay ran twice with fingerprint
`ff68afd9d8c0678d75d4882df199fd003e4eaf734e608317ea4334ad630babbb`.

The live path uses the Module 8 guard and existing writer exclusively. Outcomes were
`ALLOW` and `RESET_TO_NATIVE`; no LLM or MCP is in the physical path, no execution tool was
added, and `propose_guarded_control` remains disabled.

Verified commands include `scripts/verify_module_14a_fast.ps1`, each mode of
`scripts/run_module14a_aligned_short.py`, and `scripts/assess_module14a_results.py`.
