# Module 12 MicroTwin

Module 15 shows qualification, multi-step error, 41.67% coverage, degraded applicability,
and demand-model unavailability.

Aligned live reconciliation is `DEGRADED_BUT_USABLE`; no retraining occurred.

Module 12C completes strict dedicated replay coverage for the final 25 requirements. The MicroTwin remains offline, advisory-only, and unable to claim verified savings or comfort improvement.

The MicroTwin is a deterministic, offline, advisory surrogate for comparing Module 11 candidate plans. It is not EnergyPlus, does not execute plans, does not perform physical writes, and cannot establish verified savings or guaranteed comfort.

## Data and causal boundary

Training uses the recorded `module8-live-control` run, environment `weather-3`, zone `SPACE3-1`. Each row uses state and action information available at time *t* to predict the next zone state at *t+1*. The last row is right-censored; chronological 70/15/15 splits prevent temporal leakage. No future observed telemetry is admitted to a counterfactual rollout. See `MICROTWIN_DATA_DICTIONARY.md` for field semantics.

## Model and qualification

The thermal model is a lightweight ridge ARX model implemented in Python and stored as safe JSON. It is qualified only when its held-out MAE improves on persistence and its 12-step MAE stays within the configured limit. The current whole-building HVAC-energy proxy did not beat persistence, so demand, tariff, carbon, and peak components remain unavailable/zero rather than being fabricated.

Uncertainty uses held-out empirical residual quantiles expanded by rollout horizon. OOD checks compare each feature against training ranges. Occupied comfort is only a configured temperature-boundary risk proxy.

## Plan scoring and disagreement

Every eligible plan receives the same weather and occupancy scenario. The score combines temperature-boundary proximity, uncertainty, action churn, and OOD penalties. Lower is better, with plan ID as the deterministic tie-break. The original advisory ranking is retained separately; disagreement is reported explicitly.

## Operations

Train with `python scripts/train_microtwin.py`; validate cached artifacts with `python scripts/validate_microtwin.py`; run the demonstration with `powershell -File scripts/run_microtwin_demo.ps1`. MCP exposes six bounded status/evaluation tools. Training is not an MCP tool and `propose_guarded_control` remains disabled.

## Closure result

Module 12A reused the qualified artifact. Three final `qwen3:0.6b` sessions satisfied required evidence, and 237 tests, Ruff, strict Mypy, configuration, database, artifact, IDF and EPW checks passed with no EnergyPlus process or new physical write. Closure remains incomplete because several of the 105 replay manifest entries still rely on category-level checks rather than dedicated meaningful negative fixtures.
# Module 13 use

Module 13 reuses the five qualified Module 12 rollouts as immutable advisory inputs. It neither retrains the thermal model nor forces an unavailable demand model. No future observed telemetry is used, and no EnergyPlus simulation is started.

# Module 14 reconciliation

The selected rollout was reconciled against 12 bounded simulated points without retraining. MAE was 8.742725 °C, RMSE 8.751182 °C, and interval coverage 0%. The runtime calendar window differs from the advisory July scenario, so this is retained calibration evidence rather than a model qualification change.
