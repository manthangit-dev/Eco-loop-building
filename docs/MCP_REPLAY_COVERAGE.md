# Module 9 Replay Coverage Closure

The original specification listed 35 scenarios plus a repeated complete session. The
initial replay contained 24 calls and therefore did not fully record the requested matrix.
The additive closure replay now contains 38 meaningful calls; historical reports remain
unchanged. Every row has zero physical writes.

| # | Original scenario | Evidence | Tool | Expected / actual | Audit evidence | Status |
|---:|---|---|---|---|---|---|
| 1 | List tools | stdio smoke | discovery | 18 / 18 | smoke report | COVERED_IN_TEST |
| 2 | List runs | m9c-01 | list_available_runs | success / success | m9c-01 | COVERED_IN_REPLAY |
| 3 | Run metadata | m9c-02 | get_run_metadata | success / success | m9c-02 | COVERED_IN_REPLAY |
| 4 | Latest state | m9c-03 | get_building_state | latest / latest | m9c-03 | COVERED_IN_REPLAY |
| 5 | Historical state | m9c-04 | get_building_state | state 1 / state 1 | m9c-04 | COVERED_IN_REPLAY |
| 6 | SPACE3-1 | m9c-05 | get_zone_state | observable / observable | m9c-05 | COVERED_IN_REPLAY |
| 7 | PLENUM-1 observation | m9c-06 | get_zone_state | non-control / non-control | m9c-06 | COVERED_IN_REPLAY |
| 8 | Recent history | m9c-07 | get_recent_state_history | bounded / bounded | m9c-07 | COVERED_IN_REPLAY |
| 9 | Controller status | m9c-08 | get_controller_status | success / success | m9c-08 | COVERED_IN_REPLAY |
| 10 | Controller decisions | m9c-09 | get_controller_decisions | bounded / bounded | m9c-09 | COVERED_IN_REPLAY |
| 11 | Safety status | m9c-10 | get_safety_guard_status | success / success | m9c-10 | COVERED_IN_REPLAY |
| 12 | Safety decisions | m9c-11 | get_safety_decisions | bounded / bounded | m9c-11 | COVERED_IN_REPLAY |
| 13 | Write audit | m9c-12 | get_physical_write_audit | bounded / bounded | m9c-12 | COVERED_IN_REPLAY |
| 14 | Execution status | m9c-13 | get_energyplus_execution_status | clean / clean | m9c-13 | COVERED_IN_REPLAY |
| 15 | Error inspection | m9c-14 | inspect_energyplus_errors | bounded / bounded | m9c-14 | COVERED_IN_REPLAY |
| 16 | Approved actuators | m9c-15 | list_available_actuators | SPACE3-1 / SPACE3-1 | m9c-15 | COVERED_IN_REPLAY |
| 17 | All actuators | m9c-16 | list_available_actuators | bounded / bounded | m9c-16 | COVERED_IN_REPLAY |
| 18 | Energy summary | m9c-17 | get_run_energy_summary | diagnostic / diagnostic | m9c-17 | COVERED_IN_REPLAY |
| 19 | Compare runs | m9c-18 | compare_runs | compatible / compatible | m9c-18 | COVERED_IN_REPLAY |
| 20 | Available comfort | m9c-19 | get_comfort_evidence | coverage / coverage | m9c-19 | COVERED_IN_REPLAY |
| 21 | Unavailable metric | m9c-20 | get_comfort_evidence | unavailable / coverage count zero | m9c-20 | CONSOLIDATED |
| 22 | Valid proposal | m9c-21 | validate_control_proposal | ALLOW / ALLOW | m9c-21 | COVERED_IN_REPLAY |
| 23 | Plenum proposal | m9c-22 | validate_control_proposal | reject / plenum_zone_rejected | m9c-22 | COVERED_IN_REPLAY |
| 24 | Wrong units | m9c-23 | validate_control_proposal | reject / unit_mismatch | m9c-23 | COVERED_IN_REPLAY |
| 25 | Out of bounds | m9c-24 | validate_control_proposal | reset / out_of_absolute_bounds | m9c-24 | COVERED_IN_REPLAY |
| 26 | NaN equivalent | m9c-25 | validate_control_proposal | structured error / structured error | m9c-25 | COVERED_IN_REPLAY |
| 27 | Stale state | m9c-26 | validate_control_proposal | stale_state / stale_state | m9c-26 | COVERED_IN_REPLAY |
| 28 | Future state | m9c-27 | validate_control_proposal | future_state / future_state | m9c-27 | COVERED_IN_REPLAY |
| 29 | Unknown run | m9c-28 | get_run_metadata | structured error / structured error | m9c-28 | COVERED_IN_REPLAY |
| 30 | Invalid cursor | m9c-29 | list_available_runs | structured error / structured error | m9c-29 | COVERED_IN_REPLAY |
| 31 | Excessive result | m9c-30 | list_available_runs | structured error / structured error | m9c-30 | COVERED_IN_REPLAY |
| 32 | Unknown tool | m9c-31 | unknown_tool | structured error / unknown_tool | m9c-31 | COVERED_IN_REPLAY |
| 33 | Disabled control | m9c-32 | propose_guarded_control | denied / denied | m9c-32 | COVERED_IN_REPLAY |
| 34 | Exact duplicate | m9c-02 repeat | get_run_metadata | idempotent / idempotent | original m9c-02 | COVERED_IN_REPLAY |
| 35 | Conflicting duplicate | m9c-02 changed | get_run_metadata | rejected / conflicting_duplicate | original m9c-02 plus response | COVERED_IN_REPLAY |
| 36 | Complete replay twice | closure_1/closure_2 | complete suite | equal / equal | replay reports | COVERED_IN_TEST |

Additional closure calls independently cover fresh-expired (`m9c-35`), stale-and-expired
(`m9c-36`), command-from-future (`m9c-37`), and wrong actuator (`m9c-38`). The guard order
is future-state, command-from-future, expired-command, stale-state, identity, then numeric
validation. Thus a proposal that is both expired and stale correctly reports
`expired_command`, while a valid-TTL stale proposal reports `stale_state`.

Bypass accounting comes from `test_raw_and_dictionary_bypass_are_blocked`: two direct/raw
bypass cases and one forged `approved=true` case were executed and blocked. Live bypass
attempts were zero; all adversarial cases caused zero writes.
# Module 13 ledger replay

The ledger replay manifest contains all 156 specified scenarios with dedicated registered fixture keys. The runner requires production entry points, concrete mutations, reason/assertion checks, persistence checks where applicable, sensitivity, zero coverage gaps, and zero physical-write deltas. Two identical fingerprints are required for closure.
