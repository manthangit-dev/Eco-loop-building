# Context-aligned execution

Module 15 displays these records without recalculation and separates aligned July evidence
from the historical January/July mismatch.

Module 14A repairs the Module 14 temporal-validity gap. The original July 21 planning
context was executed against January 1 because approval schema 1 bound only a coarse
environment and file checksums. That run remains valid safety-path evidence, but its effect
and MicroTwin reconciliation are not temporally valid.

Path B selects committed Module 8 state 19147 at 2013-07-19 10:45. A disposable derived
IDF changes only the RunPeriod and weekday cooling schedule required for the 28.4 C initial
policy; canonical files remain unchanged. Approval schema 2 binds source, forecast,
15-minute timestep, RunPeriod, derived IDF, weather, plan, rollout, and ledger evaluation.

Native, shadow, and live initial conditions are identical. Shadow made zero writes. Live
held 26.9 C for 165 minutes, then made the mandatory guarded reset: one set, one reset, zero
unguarded writes. The `MEANINGFUL_EFFECT` result measured 11 differing setpoint timesteps,
a 1.2031 C maximum temperature response, 2,547,870.77 J aggregate facility timestep-energy
difference, and 70,690.96 J HVAC timestep-energy difference. These are not annual savings.

The aligned 12-point reconciliation excluded zero points: MAE 0.3490 C, RMSE 0.4112 C,
bias -0.2776 C, 41.67% interval coverage, 100% risk agreement, and 91.67% setpoint
agreement. Applicability is `DEGRADED_BUT_USABLE`; no retraining occurred. Module 15 is
outside this repair.
