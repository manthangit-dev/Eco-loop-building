# Project Scope

## Interpretation and objective

ThermoLedger AI is a hackathon prototype for autonomous building control in an EnergyPlus digital twin. Its objective is to reduce energy and peak demand while preserving occupied comfort fairly across zones.

## Users and closed loop

Target users are hackathon evaluators, building-energy researchers, and prototype operators. The closed loop reads EnergyPlus state, structures it in a state bus, plans candidate actions, validates them deterministically, injects a validated action, observes outcomes, and records feedback for critique.

## MVP features

- Comfort-debt ledger and zone-flexibility scoring.
- Thermal-battery pre-cooling, coasting, and restoration strategy.
- Tournament of comfort-first, balanced, and energy-aggressive candidates.
- Deterministic safety guard and LLM-independent fallback.

## Inputs, sensors, and actuators

Required sensors: zone mean air temperature, zone occupant count, outdoor dry-bulb temperature, outdoor relative humidity, facility electrical demand and consumption, HVAC/cooling energy where available, and simulation date/time. Optional sensors are Fanger PMV, zone CO2, and zone relative humidity. Local reproducible tariff, carbon-intensity, and occupancy-disturbance CSV files are planned inputs.

The primary actuator is zone cooling set-point; ventilation multiplier is secondary. The interval is 15 simulation minutes. A representative day is the live demonstration period and a representative week is the final evaluation period.

## Baseline comparison

Baseline and AI-controlled simulations will be run separately using the identical building, weather, occupancy, external signals, and periods. Outputs will be overlaid and compared. Simultaneous dual instances are a stretch goal only.

## Boundaries and non-goals

This MVP is not a commercial BMS, physical deployment, custom-trained LLM, reinforcement-learning project, multi-building cloud platform, mobile app, live-grid-API system, production safety-certified controller, universal HVAC controller, or 3D visualisation product.

## Stretch goals, assumptions, and boundaries

Stretch goals include dual-instance execution and optional PMV/CO2 sensing. Assumptions awaiting verification: EnergyPlus 26.1.0 supports the selected IDF on the host, required handles are exposed, and local hardware can run a suitable Ollama model. This repository currently covers planning only; functional integration begins in later modules.
