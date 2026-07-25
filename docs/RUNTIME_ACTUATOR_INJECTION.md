# Module 5: Safe Runtime Actuator Injection

Module 5 is a deterministic actuator-functionality experiment. It proves that Python
can discover, acquire, write, observe, and reset exactly one EnergyPlus actuator. It
is not an autonomous controller or an optimisation experiment.

## Discovery and selection

The persisted catalog comes from `list_available_api_data_csv` during a real
Module 4 run. The discovery CLI classified all 1,213 actuator records and found
five eligible isolated cooling actuators:

`Zone Temperature Control / Cooling Setpoint / SPACE1-1..SPACE5-1 / [C]`.

`SPACE3-1` was selected deterministically. At the hottest occupied summer-afternoon
record (July 19), it had the highest zone temperature among eligible zones. During
the intervention it had 11 occupants, versus zero for `PLENUM-1`. The other five
zones were not selected because Module 5 permits only one actuator; the plenum was
ineligible, and the other occupied spaces ranked below `SPACE3-1`.

The exact approved actuator is:

- Component type: `Zone Temperature Control`
- Control type: `Cooling Setpoint`
- Unique key and zone: `SPACE3-1`
- Units: `C` (`[C]` in the discovery catalog)
- Runtime handle: `418`

Sensor handles read reported variables; actuator handles write a bounded external
override. The registry exposes only this exact configured triple and never accepts
arbitrary actuator names from the CLI.

## Plan and callbacks

The fixed weather-run window is July 19, 14:00–15:30, aligned to six 15-minute zone
timesteps. Module 4 evidence showed 35°C outdoor air, approximately 20 kW facility
demand, active occupancy, and cooling-relevant zone temperatures around 23.9°C.

The control run verified `Zone Thermostat Cooling Setpoint Temperature` at 23.9°C.
The requested offset was +1.0°C, producing an approved 24.9°C target within the
22–26°C absolute bounds and 1.0°C maximum offset.

`callback_after_predictor_before_hvac_managers` applies the override. It checks API
readiness, warmup and weather environment, occupancy, exact handle identity, finite
bounds, and API error flags. Repeated system-timestep calls reapply the same fixed
value. `callback_end_zone_timestep_after_zone_reporting` observes the effective
set-point. Exceptions are contained inside both callbacks.

At the end of the window, `reset_actuator` releases the override; no guessed
baseline value is written. A final cleanup reset is attempted only while the state
is active and only if an override remains active.

## Runs, events, and validation

The control and intervention runs use the same annual IDF, Chicago weather, API
runner, and complete Module 4 sensor collector. Outputs are under:

- `data/output/module_5_actuator_test/control/current`
- `data/output/module_5_actuator_test/intervention/current`

Each contains the annual sensor JSONL/CSV plus actuator discovery, manifest,
streamed UTF-8 JSONL/CSV events, run summary, and EnergyPlus outputs. Events include
discovery/acquisition, control observations, applications/reapplications, reset,
API/callback errors, rejected writes, and post-reset observations.

Run everything with:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/verify_actuator_injection.ps1
```

Independent checks:

```powershell
python scripts/validate_actuator_test.py
python scripts/compare_actuator_runs.py
```

## Verified results

Both annual runs exited zero with 35,040 sensor snapshots, zero warnings, severe
errors, fatal errors, API errors, and callback errors.

- Control: handle acquired; 0 set calls and 0 resets.
- Intervention: 9 set calls over 8 unique system-timestep periods; 1 reset at
  15:30; 0 out-of-window and 0 unapproved writes.
- Effective set-point: 23.9°C before; 24.9°C during; 23.9°C after reset.
- Mean target-zone temperature during the window: 23.942°C control versus
  24.720°C intervention, a measured +0.779°C response.
- Mean interval facility energy: 17,662,679 J control versus 17,412,283 J
  intervention.
- Mean interval HVAC energy: 560,179 J control versus 526,302 J intervention.

Electricity differences are diagnostics for this short functionality experiment;
they are not energy savings. Source IDF, baseline IDF, and weather checksums stayed
unchanged, and the EnergyPlus installation remained clean.

Limitations include one predefined zone/window, a single example building, a short
intervention, and system-timestep reapplication counts that exceed zone-timestep
counts. The implementation is deterministic. No autonomous controller, safety
decision engine, LLM, ventilation control, or verified energy-saving claim exists.

