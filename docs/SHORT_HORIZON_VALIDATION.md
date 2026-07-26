# Short-Horizon Validation

Module 15 labels this short-horizon and explicitly shows increased electricity, never savings.

Module 14A's aligned July 19 evidence supersedes the original mismatched effect conclusion only.

Three compatible bounded EnergyPlus 26.1 runs captured 12 zone timesteps each. The native reference took 1.359 s, shadow 1.390 s, and approved live control 1.422 s. Shadow recorded Module 8 `ALLOW` and zero writes. Live control recorded `ALLOW`, one guarded set, `RESET_TO_NATIVE`, one guarded reset, and zero unguarded writes. All runs exited cleanly; annual run count was zero.

Native, shadow, and live temperature summaries were identical for this window: minimum 16.700066 °C, maximum 17.645166 °C, mean 16.977763 °C, with zero occupied upper-boundary risks. Facility electricity was 9,196,962.049 J and HVAC electricity 4,064,880.774 J in both native and live runs, producing a scenario-specific short-window difference of 0 J.

Simulation reconciliation used 12 points from rollout `645374bcef394cabec747564610c2073f49159bf0e088661b34d6c24d4d56a1e`. MAE was 8.742725 °C, RMSE 8.751182 °C, bias −8.742725 °C, and empirical interval coverage 0%. The key limitation is that the bounded available runtime window is not the July advisory scenario. This evidence is retained for future calibration; the MicroTwin was not retrained.

These are short-horizon EnergyPlus simulation outcomes. They do not establish annual savings, real-building savings, production optimisation, or guaranteed comfort improvement.
