# Module 3 Python EnergyPlus API Runner

## Purpose

Module 3 introduces a typed Python 3.12 runner that executes the verified Module 2 baseline
through `EnergyPlusAPI().runtime.run_energyplus`. Unlike Module 2's executable orchestration,
the simulation now runs through the installed EnergyPlus Runtime API and exposes bounded
lifecycle, progress, and console-message callbacks. It still performs no sensing or control.

## API loading

The loader resolves `ENERGYPLUS_HOME` from the process and then the ignored `.env`, validates
the installation and `pyenergyplus` directory, temporarily adds the installation root to
Python import resolution, and retains the Windows DLL-directory handle for the API lifetime.
It imports the installation-provided `pyenergyplus`; nothing is installed through pip.

EnergyPlus 26.1's `EnergyPlusAPI` object does not expose an `api_path()` method. The verified
loader reports the real loaded library from its `ctypes.CDLL` object:
`C:\EnergyPlusV26-1-0\EnergyPlusAPI.dll`. API version 0.2 and EnergyPlus version 26.1 are
checked before execution.

## State and callback lifecycle

Every run creates a fresh state with `new_state()`, verifies API compatibility, registers new
callbacks, calls `run_energyplus`, clears callbacks, and deletes the state in `finally`
cleanup. A process-local lock rejects concurrent runs. States are never reused.

Registered callbacks are limited to:

- simulation progress;
- EnergyPlus console messages;
- beginning of a new environment;
- completion of environment warmup.

Messages are decoded with UTF-8 replacement, normalized, length-bounded, stored in a bounded
in-memory list, and written incrementally to `energyplus_api_messages.log`. Exceptions are
contained inside callbacks and recorded. No callback calls `api.exchange`, reads a sensor,
obtains an actuator handle, sets an actuator, or modifies simulation state.

## Arguments and output safety

The approved API arguments mirror Module 2:

```text
-d <module-3-output> -p thermoledger -s C -w <verified-weather> -r <verified-idf>
```

The executable name is deliberately excluded. The current output is restricted to
`data/output/module_3_api_runner/current`. A prior run is moved to a timestamped archive; no
directory outside the Module 3 output root is removed or cleaned.

Model and weather resolution follows configured, checksum-verified paths. Tracked
configuration contains no user-specific absolute paths.

## Timeout and cancellation

`run_energyplus` executes in one controlled worker thread. At timeout the runner calls
`runtime.stop_simulation(state)` and allows the configured grace period. Because safely
deleting a state still in use is forbidden, the runner then waits for the API call to return
before clearing callbacks and deleting state. Thus this is a safe soft timeout, not a
hard-duration guarantee. `KeyboardInterrupt` similarly requests `stop_simulation` and waits
for orderly return. Partial logs and outputs are preserved and timed-out/cancelled runs fail.

## Results, validation, and parity

`run_metadata.json` records bounded callback evidence, timings, checksums, arguments, API
identity, exit code, cleanup evidence, and validation/comparison status. It contains no
environment dump or unbounded console output.

The Module 2 validator is reused with an explicit safe Module 3 output root. Structural
comparison checks versions, checksums, exit/error counts, required output types, CSV header
and row count, first/last timestamp, completion evidence, SQL/RDD/MDD output, and hashes. Hash
differences alone would be reported rather than treated as optimization evidence.

## Commands

Run the API baseline:

```powershell
python scripts/run_api_baseline.py --config config/api_runner.yaml
```

Run complete verification:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/verify_api_runner.ps1
```

Run unit/static checks:

```powershell
python -B -m pytest -p no:cacheprovider
python -m ruff check . --no-cache
python -m mypy --no-incremental src scripts tests
```

The ordinary unit tests use fakes and do not run EnergyPlus. The command-line run above is the
real integration test.

## Verified result

The first successful real API run on 2026-07-25 reported:

- EnergyPlus exit code 0;
- 367 progress events, finishing at 100%;
- 122 message events;
- 1 environment-start event;
- 5 warmup-complete events;
- 0 callback errors and 0 truncated messages;
- callbacks cleared and state deleted;
- 0 warnings, 0 severe errors, and 0 fatal errors;
- output validation passed;
- Module 2 structural comparison passed;
- 8,760 matching CSV rows, identical first/last timestamps, and byte-identical primary CSV.

## Troubleshooting and boundaries

- **Import failure:** verify `ENERGYPLUS_HOME/pyenergyplus` and activate the repository
  Python 3.12 environment.
- **DLL failure:** verify `EnergyPlusAPI.dll` exists in the installation root and matches the
  installation's Python wrapper.
- **Wrong version:** the loader requires reported EnergyPlus version 26.1.
- **Cleanup failure:** do not start another in-process run; inspect metadata and restart the
  Python process after resolving the underlying API error.
- **Callback error:** inspect `callback_errors` and the bounded message log; callback
  exceptions always fail verification.
- **Timeout:** a stop is requested, but cleanup waits for the C API to return safely.

Module 3 contains no Data Exchange API use, sensor extraction, actuator access, HVAC control,
AI control, optimization, or energy-saving claim. Those remain later-module concerns.

