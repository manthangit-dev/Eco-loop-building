# Module 4: Live Sensor Extraction

Module 4 adds a read-only Data Exchange API layer to the unchanged Module 3
EnergyPlus run. Lifecycle callbacks record progress, messages, environments, and
warmup completion; `callback_end_zone_timestep_after_zone_reporting` separately
captures reported state at each zone timestep.

## Data flow and safety

Variables are requested before `run_energyplus`. Handles are acquired once, only
after `api_data_fully_ready` is true. The callback skips warmup and accepts only
EnergyPlus simulation kind `3` (Weather File Run Period). API error flags are reset
and checked around handle acquisition and reads. Numeric zero is a valid reading.
Callback exceptions are contained and recorded.

Only variable/meter and simulation-time Data Exchange methods are used. The module
never acquires, reads, or writes an actuator or internal-variable handle, and it
does not modify the IDF, weather file, or EnergyPlus installation.

## Sensor registry

Required live readings and units are:

- `Zone Mean Air Temperature` (`C`) for all six zones.
- `Zone People Occupant Count` (`person`) for occupied zones. `PLENUM-1` has no
  `People` object and no runtime key; its configured, model-verified occupancy is
  therefore `0.0`.
- `Site Outdoor Air Drybulb Temperature` (`C`) and
  `Site Outdoor Air Relative Humidity` (`percent`), key `Environment`.
- `Facility Total Electricity Demand Rate` (`W`), key `Whole Building`.
- `ElectricityPurchased:Facility` (`J`), the facility purchased-electricity meter.
- `Electricity:HVAC` (`J`).

Optional live readings are zone relative humidity and cooling, heating, fans,
pumps, interior-equipment, and interior-lighting electricity meters. PMV and CO2
are disabled because the RDD does not expose them (and contaminant simulation is
off). EnergyPlus 26.1 lists `Electricity:Facility` in the API catalog but returns
handle `-1`; it remains an audited unavailable optional sensor. Because this
baseline has no onsite generation, the required facility reading uses the exact
verified `ElectricityPurchased:Facility` meter.

Meter readings are interval energy in joules, not cumulative annual totals. No
savings are calculated.

## Schema and files

Each immutable snapshot contains sequence; environment/calendar/time/timestep
identity; outdoor and building readings; one typed state per model zone; optional
availability; and contained errors. JSONL stores one compact UTF-8 object per line.
CSV uses deterministic zone-qualified columns. Writers stream, flush every 100
snapshots, and atomically publish temporary files on close.

Outputs are in `data/output/module_4_sensor_extraction/current/`:

- `sensor_snapshots.jsonl` and `sensor_snapshots.csv`
- `available_api_data.csv` and `sensor_manifest.json`
- `sensor_extraction_summary.json` and `sensor_validation_summary.json`
- `sensor_baseline_comparison.json`

## Run and verify

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/verify_sensor_extraction.ps1
```

Independent validation and comparison:

```powershell
python scripts/validate_sensor_extraction.py --sensor-config config/sensors.yaml
python scripts/compare_sensor_run_to_baseline.py --api-config config/api_runner.yaml
```

## Verified integration result

The annual Chicago weather run exited `0` with zero severe, fatal, callback,
sensor-read, and API exchange errors. Four zone timesteps per hour over the actual
365-day run period gives an expected `365 * 24 * 4 = 35,040` snapshots; actual was
35,040. The first timestamp was `env=3; day=1; 00:15; step=1`; the last was
`env=3; day=365; 23:60; step=4`. All six zones were present. Model and weather
checksums were unchanged, and physical comparison with Module 3 passed.

Known limitations are the explicit plenum occupancy fallback and inaccessible
`Electricity:Facility` handle above. Extraction is entirely read-only. No actuator
control, AI, optimization, or energy-saving result exists in Module 4.
