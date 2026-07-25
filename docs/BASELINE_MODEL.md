# Module 2 Baseline Model

## Selection and provenance

The baseline uses EnergyPlus 26.1.0's `5ZoneAirCooled.idf` example because it is a compact,
auditable multi-zone office with a central VAV system and enough zone diversity for later
fairness experiments. The installation file was copied byte-for-byte to
`models/source/5ZoneAirCooled_v26_1_original.idf`. Its SHA-256 is
`0187cf7f2ca9c27c43d435a68a8c66a557a43678846813a7e21463a0b0c716cd`, identical to
the installed example at verification time.

The file declares EnergyPlus version 26.1 and building name `Building`. Its header describes a
single-floor, 463.6 m² rectangular office with four perimeter conditioned zones, one interior
conditioned zone, and a return plenum. It states 50 people, 7,500 W of lighting, office
equipment, infiltration, windows on four facades, and a building orientation 30 degrees east
of north.

## Zones

The six `Zone` objects are:

1. `PLENUM-1`
2. `SPACE1-1`
3. `SPACE2-1`
4. `SPACE3-1`
5. `SPACE4-1`
6. `SPACE5-1`

The five `SPACE` zones are conditioned; `PLENUM-1` is the return plenum.

## HVAC, schedules, and controls

The model contains one standard VAV air loop with outside air, one variable-volume supply fan,
five VAV reheat terminals, hot-water reheat coils, two water cooling coils, seven water
heating coils, two variable-speed pumps, one hot-water boiler, and one electric chiller with
an air-cooled condenser. Two plant loops serve chilled and hot water. Equipment is autosized.

The source uses compact schedules for occupancy, internal loads, HVAC availability, and
thermostat set points. Module 2 did not change any schedule, thermostat, sizing, topology,
equipment, construction, geometry, infiltration, ventilation, or control object.

## Run configuration

- RunPeriod: `Run Period 1`, January 1 through December 31
- Start day: Tuesday
- Timestep: 4 per hour (15 minutes)
- SimulationControl: zone, system, and plant sizing enabled; weather-file run enabled;
  design-day simulation disabled
- Weather: `USA_IL_Chicago-OHare.Intl.AP.725300_TMY3.epw`
- Weather SHA-256:
  `c7d4efcf93ba316a1d874352e743df5cf137ba5c0e3459eb2dc4b5442d5b7f5c`

The source header refers to an older Chicago TMY2 file. Module 2 uses the required EnergyPlus
26.1-distributed Chicago O'Hare TMY3 file. The location remains Chicago, but results should be
identified with this exact TMY3 provenance rather than described as the source header's TMY2
weather.

## Preservation and reporting

`models/baseline/thermoledger_5zone_baseline.idf` began as a byte-identical source copy.
The only derived-model change is:

```idf
Output:SQLite,
  SimpleAndTabular;
```

This option was verified in the installed EnergyPlus 26.1 IDD. The source already requested 41
hourly output variables, `Output:VariableDictionary, Regular`,
`Output:Table:SummaryReports, AllSummaryAndSizingPeriod`, and HTML table style. The exact
difference is recorded in `models/baseline/baseline_reporting_changes.diff`.

No physical-model modification or control optimization was introduced. The derived SHA-256 is
`6ddd3c29c552b44d2f83eff1338eec194ca2fede9d9f2860dc4492edc1005cea`.

## Verified result and limitations

On 2026-07-25, both the preserved-source smoke run and derived baseline completed with exit
code 0, zero warnings, zero severe errors, and zero fatal errors. The final run generated
non-empty ERR, EIO, CSV, HTML, SQL, RDD, MDD, ESO, and MTR outputs.

This is an example building, not a calibrated real facility. Its schedules, loads, envelope,
systems, and weather are fixed baseline assumptions. A successful run establishes technical
reproducibility; it does not establish real-building accuracy or any energy saving. Later
modules will consume this preserved baseline but must not rewrite it in place.

