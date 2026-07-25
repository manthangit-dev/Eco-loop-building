# Module 2 Baseline Execution

## Prerequisites

Complete Module 1 first. Native Windows requires the repository `.venv` with Python 3.12,
EnergyPlus 26.1.x, and a local `.env` containing `ENERGYPLUS_HOME`. The official Chicago
O'Hare TMY3 file must exist in the repository input directory or the configured EnergyPlus
weather locations.

Activate the environment:

```powershell
.\.venv\Scripts\Activate.ps1
python --version
```

## Path resolution

The runner resolves its repository root from its own location. It resolves `ENERGYPLUS_HOME`
from the current process and then `.env`. Model paths come from `config/baseline.yaml`.
Weather resolution order is:

1. `weather/input/<configured filename>`
2. `ENERGYPLUS_WEATHER_PATH`
3. `ENERGYPLUS_HOME\WeatherData\<configured filename>`

No user-specific path is stored in tracked configuration. The repository EPW copy is ignored
by Git; another developer should copy the identically named official file from an EnergyPlus
26.1 `WeatherData` directory and verify the manifest checksum.

## Run and validate

Run the required source smoke test and final derived baseline:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/run_baseline.ps1
```

The script safely archives an existing `smoke` or `current` directory below
`data/output/module_2_baseline/archive`. `-NoClean` instead refuses to reuse an existing output
directory.

Validate an already completed final run independently:

```powershell
python scripts/validate_baseline.py --config config/baseline.yaml
```

Final results are written to `data/output/module_2_baseline/current`; generated files and
archives are ignored by Git.

## Output files

- **ERR**: diagnostic messages and authoritative final warning/severe summary.
- **EIO**: model, sizing, envelope, system, and simulation initialization details.
- **CSV**: requested time-series results converted from ESO.
- **SQL**: simple and tabular SQLite reporting output.
- **HTML**: human-readable tabular summary reports.
- **RDD**: available output-variable dictionary for this model.
- **MDD**: available meter dictionary for this model.
- **ESO/MTR**: native time-series and meter result streams.

Warnings are always reported and require review. Any severe or fatal error fails validation.
The verified Module 2 run had zero warnings, severe errors, and fatal errors.

## Reproduction and troubleshooting

Before reproduction, verify:

```powershell
python scripts/check_environment.py
python -B -m pytest -p no:cacheprovider
python -m ruff check . --no-cache
python -m mypy --no-incremental scripts tests
```

- **Weather mismatch:** use the exact configured Chicago O'Hare filename and compare its
  SHA-256 with `models/MODEL_MANIFEST.json`.
- **IDF version mismatch:** use EnergyPlus 26.1 and restore the preserved source if its
  checksum changes.
- **Output permission failure:** ensure the current user can write below `data/output`.
- **Executable failure:** confirm `ENERGYPLUS_HOME\energyplus.exe --version` reports 26.1.
- **Missing SQL or HTML:** confirm the derived model retains `Output:SQLite,
  SimpleAndTabular` and the source summary-report/table-style objects.
- **Failed smoke run:** inspect `data/output/module_2_baseline/smoke/smoke.err`; do not edit
  building physics merely to suppress an error.

Module 2 uses only the EnergyPlus command-line executable. It does not implement the Python
runtime API, callbacks, sensors, actuators, controllers, AI, or optimization.

