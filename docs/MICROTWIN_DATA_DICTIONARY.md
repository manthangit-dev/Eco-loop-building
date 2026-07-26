# MicroTwin data dictionary

Module 12 profiles the recorded `module8-live-control` SQLite state database.
SPACE3-1 records occur every 15 simulated minutes (four zone timesteps/hour).
Features at sequence `t` predict targets at `t+1`; the final annual row is
right-censored and excluded. Environment transitions and warmup rows are excluded.

The causal feature order is current SPACE3-1 temperature (C), outdoor dry-bulb (C),
effective cooling setpoint (C), occupancy (people), previous whole-HVAC electricity
(J per zone timestep), causal one-step changes for temperature/outdoor/setpoint/HVAC,
and hour sine/cosine. Future actual temperature, demand,
occupancy, controller/safety outcomes, and experimental setpoints are prohibited.
Counterfactual future inputs come only from candidate actions and Module 11 scenarios.

The HVAC metric is a whole-building HVAC electricity proxy and cannot be attributed
entirely to SPACE3-1. Facility demand is excluded from causal attribution. Exact
measured counts and availability are in `outputs/module12/microtwin_data_profile.json`.
