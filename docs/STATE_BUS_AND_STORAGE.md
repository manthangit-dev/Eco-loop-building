# State Bus and SQLite Storage

## Purpose and implemented flow

Module 6 converts each Module 4 `SensorSnapshot` into an immutable canonical
`BuildingState`, publishes it through a bounded thread-safe bus, and persists it to
SQLite without database I/O on the EnergyPlus callback thread.

```text
EnergyPlus sensor callback
        |
SensorSnapshot
        |
State normaliser
        |
Canonical BuildingState
        |
Thread-safe StateBus
       /             \
Bounded history    Persistence worker
                          |
                    SQLite database
```

A `SensorSnapshot` is the direct EnergyPlus observation. A `BuildingState` adds schema
version, run identity, deterministic sequence and fingerprint, stable zone IDs,
classification evidence, explicit availability, and quality issues. This stable
boundary prevents consumers from depending on raw API naming or callback objects.

## Canonical schema and classification

The immutable dataclasses model the simulation clock, outdoor state, building energy,
and per-zone state. EnergyPlus clock values are preserved; the verified source contains
floating-point-derived minute values through 68. Outdoor dry-bulb/humidity and required
energy values must be finite. Zone state includes exact name, stable ID, classification,
temperature, occupancy, humidity, and optional PMV, CO2, and effective setpoint.

`PLENUM-1` is `PLENUM`, is not occupancy-capable, and preserves verified zero occupancy.
`SPACE1-1` through `SPACE5-1` are `OCCUPIED_CONDITIONED`. Valid zero is never treated as
missing. Unavailable optional values remain null with explicit availability records.
Required non-finite values, duplicate or missing zones, unsupported schemas, and
decreasing sequences are rejected. Quality issues preserve source sensor errors.

Fingerprints are SHA-256 hashes of sorted canonical raw snapshot JSON. They are stable
between replay and live sensing and exclude capture time and run identity.

## StateBus and persistence

The bus retains 256 states in a bounded deque; evictions are counted. It supports
latest, recent, range, timed waiting, subscribe, and unsubscribe. Subscriber callbacks
execute outside the lock and failures are isolated and recorded. Duplicate/decreasing
sequences are rejected and gaps are counted.

SQLite schema v1 has `simulation_runs`, `building_states`, `zone_states`,
`sensor_availability`, `state_quality_issues`, and `storage_events`. Indexed access
covers run/sequence, run/time, state zones, and zone history. Foreign keys and cascade
deletion are enabled. WAL, parameterized SQL, batches of 100, transactions, rollback,
integrity checks, and read-only inspection connections are used.

The dedicated persistence thread owns SQLite. Its queue is bounded at 512 entries.
Producers wait at most five seconds; timeout is an explicit failure, never a silent
drop. Shutdown unsubscribes, persists the final batch, finalizes run metadata, drains
the queue, and closes SQLite.

## Commands

```powershell
python scripts/replay_sensor_states.py --state-config config/state_bus.yaml
python scripts/run_state_bus_integration.py --api-config config/api_runner.yaml --sensor-config config/sensors.yaml --state-config config/state_bus.yaml
python scripts/validate_state_storage.py --state-config config/state_bus.yaml --mode replay
python scripts/validate_state_storage.py --state-config config/state_bus.yaml --mode live
python scripts/inspect_state_database.py --state-config config/state_bus.yaml --mode live --recent 5 --zone-id space1_1
```

Inspection uses predefined parameterized read-only queries; no arbitrary SQL CLI exists.

## Verified results — 2026-07-25

| Result | Full replay | Live EnergyPlus |
| --- | ---: | ---: |
| Building states | 35,040 | 35,040 |
| Zone rows | 210,240 | 210,240 |
| Queue high-water mark | 512 | 512 |
| Database size | 498,937,856 bytes | 498,462,720 bytes |
| Persistence / subscriber errors | 0 / 0 | 0 / 0 |
| Queue drained | Yes | Yes |
| Integrity / foreign keys | `ok` / 0 | `ok` / 0 |
| Module 4 physical comparison | Not applicable | Passed; primary CSV byte-identical |

The real annual run exited zero, collected/normalized/published/persisted every state,
had zero callback/API errors, and used unchanged model/weather checksums. Both modes
recorded zero actuator access and zero control decisions.

## Limitations and boundaries

Annual databases are about 499 MB because full canonical JSON and normalized rows are
retained. The queue reached its configured capacity without timeout or loss, so write
throughput remains a risk. Concurrent-reader load, WAL leftovers, interrupted shutdown,
corruption, sequence/schema mismatch, and accidental database commits require continued
monitoring. PMV, CO2, and effective setpoint are unavailable in the current stream.

There is no controller, comfort-debt ledger, AI/LLM, or dashboard. Module 6 makes no
autonomous decision and no energy-saving claim. Module 7 remains pending.
# Schema 8 ledger persistence

Schema 8 adds comfort accounts/entries, debt and repayment records, fairness assessments, Thermal Bank accounts/transactions, plan evaluations, rankings, and ledger sessions. Migration is additive; persistence uses transactions, foreign keys, and idempotent identifiers. No telemetry or earlier module tables are removed.

# Schema 9 execution persistence

Schema 9 additively stores immutable approvals, sessions, transitions, exactly-once actions, guarded writer attempts, fallback events, native resets, compatible-run comparisons, and per-timestep simulation reconciliation. Integrity and foreign-key checks pass with zero orphans.
