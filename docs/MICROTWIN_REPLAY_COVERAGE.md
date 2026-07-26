# MicroTwin Replay Coverage

Module 12C addendum: all 25 gaps documented below were subsequently resolved with dedicated mutation-sensitive executable fixtures. The final audit is `outputs/module12c/final_replay_fixture_audit.json`; the Module 12B text remains honest history.

Module 12B expands the canonical manifest from 105 to 150 scenarios and adds 64 dedicated executable mappings. The stricter final audit still identifies original negative requirements incorrectly represented by shared category checks. Those are coverage gaps; the provisional 150/150 replay result is not sufficient for closure. Authoritative current classifications are in `outputs/module12b/replay_fixture_audit.json`.

| Requirement | Description | Category | Status |
|---|---|---|---|
| MT12-001 | Valid telemetry source. | data_alignment | CONSOLIDATED |
| MT12-002 | Missing source run. | data_alignment | CONSOLIDATED |
| MT12-003 | Wrong environment. | data_alignment | CONSOLIDATED |
| MT12-004 | Missing target zone. | data_alignment | CONSOLIDATED |
| MT12-005 | Warmup rows excluded. | data_alignment | CONSOLIDATED |
| MT12-006 | API-not-ready rows excluded. | data_alignment | CONSOLIDATED |
| MT12-007 | Final right-censored row excluded. | data_alignment | CONSOLIDATED |
| MT12-008 | System-timestep aggregation. | data_alignment | CONSOLIDATED |
| MT12-009 | Duplicate callback records. | data_alignment | CONSOLIDATED |
| MT12-010 | Non-monotonic timestamps. | data_alignment | CONSOLIDATED |
| MT12-011 | Cross-environment transition. | data_alignment | CONSOLIDATED |
| MT12-012 | Action-to-next-state alignment. | data_alignment | CONSOLIDATED |
| MT12-013 | Missing occupancy. | data_alignment | CONSOLIDATED |
| MT12-014 | Missing outdoor temperature. | data_alignment | CONSOLIDATED |
| MT12-015 | Missing setpoint. | data_alignment | CONSOLIDATED |
| MT12-016 | Missing demand metric. | data_alignment | CONSOLIDATED |
| MT12-017 | Invalid units. | data_alignment | CONSOLIDATED |
| MT12-018 | NaN rejected. | data_alignment | CONSOLIDATED |
| MT12-019 | Infinity rejected. | data_alignment | CONSOLIDATED |
| MT12-020 | Prohibited future feature detected. | data_alignment | CONSOLIDATED |
| MT12-021 | Chronological split. | splitting_preprocessing | CONSOLIDATED |
| MT12-022 | Stable split fingerprint. | splitting_preprocessing | CONSOLIDATED |
| MT12-023 | No random shuffle. | splitting_preprocessing | CONSOLIDATED |
| MT12-024 | Train-only preprocessing. | splitting_preprocessing | CONSOLIDATED |
| MT12-025 | Validation boundary. | splitting_preprocessing | CONSOLIDATED |
| MT12-026 | Test boundary. | splitting_preprocessing | CONSOLIDATED |
| MT12-027 | No environment leakage. | splitting_preprocessing | CONSOLIDATED |
| MT12-028 | Feature order determinism. | splitting_preprocessing | CONSOLIDATED |
| MT12-029 | Missing-value policy. | splitting_preprocessing | CONSOLIDATED |
| MT12-030 | OOD metadata construction. | splitting_preprocessing | CONSOLIDATED |
| MT12-031 | Persistence baseline. | training_artifacts | CONSOLIDATED |
| MT12-032 | Thermal model fit. | training_artifacts | CONSOLIDATED |
| MT12-033 | Demand model fit when available. | training_artifacts | CONSOLIDATED |
| MT12-034 | Demand model unavailable path. | training_artifacts | CONSOLIDATED |
| MT12-035 | Stable coefficients. | training_artifacts | CONSOLIDATED |
| MT12-036 | Repeated training fingerprint. | training_artifacts | CONSOLIDATED |
| MT12-037 | Invalid configuration. | training_artifacts | CONSOLIDATED |
| MT12-038 | Singular-feature handling. | training_artifacts | CONSOLIDATED |
| MT12-039 | Constant feature. | training_artifacts | CONSOLIDATED |
| MT12-040 | Insufficient data. | training_artifacts | CONSOLIDATED |
| MT12-041 | Qualification pass. | training_artifacts | CONSOLIDATED |
| MT12-042 | Qualification failure. | training_artifacts | CONSOLIDATED |
| MT12-043 | Model artifact checksum. | training_artifacts | CONSOLIDATED |
| MT12-044 | Unsafe artifact format rejected. | training_artifacts | CONSOLIDATED |
| MT12-045 | One-step metrics. | validation | CONSOLIDATED |
| MT12-046 | Three-step rollout. | validation | CONSOLIDATED |
| MT12-047 | Six-step rollout. | validation | CONSOLIDATED |
| MT12-048 | Twelve-step rollout. | validation | CONSOLIDATED |
| MT12-049 | Persistence comparison. | validation | CONSOLIDATED |
| MT12-050 | Occupied error group. | validation | CONSOLIDATED |
| MT12-051 | Unoccupied error group. | validation | CONSOLIDATED |
| MT12-052 | Residual interval. | validation | CONSOLIDATED |
| MT12-053 | Interval coverage. | validation | CONSOLIDATED |
| MT12-054 | Bias accumulation. | validation | CONSOLIDATED |
| MT12-055 | Worst-case sequence. | validation | CONSOLIDATED |
| MT12-056 | Held-out test not used for fitting. | validation | CONSOLIDATED |
| MT12-057 | NATIVE_HOLD rollout. | counterfactual_rollout | CONSOLIDATED |
| MT12-058 | COMFORT_FIRST rollout. | counterfactual_rollout | CONSOLIDATED |
| MT12-059 | BALANCED rollout. | counterfactual_rollout | CONSOLIDATED |
| MT12-060 | PRECONDITION_BEFORE_PEAK rollout. | counterfactual_rollout | CONSOLIDATED |
| MT12-061 | VACANCY_RELAXATION rollout. | counterfactual_rollout | CONSOLIDATED |
| MT12-062 | OCCUPIED_RECOVERY rollout. | counterfactual_rollout | CONSOLIDATED |
| MT12-063 | Same forecast across plans. | counterfactual_rollout | CONSOLIDATED |
| MT12-064 | Candidate setpoint trajectory applied. | counterfactual_rollout | CONSOLIDATED |
| MT12-065 | Future actual temperature not used. | counterfactual_rollout | CONSOLIDATED |
| MT12-066 | Future actual energy not used. | counterfactual_rollout | CONSOLIDATED |
| MT12-067 | Empirical uncertainty propagated. | counterfactual_rollout | CONSOLIDATED |
| MT12-068 | Boundary risk calculated. | counterfactual_rollout | CONSOLIDATED |
| MT12-069 | OOD input detected. | counterfactual_rollout | CONSOLIDATED |
| MT12-070 | Strongly OOD plan not ranked. | counterfactual_rollout | CONSOLIDATED |
| MT12-071 | Physical-write count zero. | counterfactual_rollout | CONSOLIDATED |
| MT12-072 | MicroTwin score reproducible. | scoring_ranking | CONSOLIDATED |
| MT12-073 | NATIVE_HOLD reference. | scoring_ranking | CONSOLIDATED |
| MT12-074 | Temperature-risk penalty. | scoring_ranking | CONSOLIDATED |
| MT12-075 | Demand-proxy component. | scoring_ranking | CONSOLIDATED |
| MT12-076 | Peak-alignment component. | scoring_ranking | CONSOLIDATED |
| MT12-077 | Tariff proxy. | scoring_ranking | CONSOLIDATED |
| MT12-078 | Carbon proxy. | scoring_ranking | CONSOLIDATED |
| MT12-079 | Uncertainty penalty. | scoring_ranking | CONSOLIDATED |
| MT12-080 | OOD penalty. | scoring_ranking | CONSOLIDATED |
| MT12-081 | Stable ranking. | scoring_ranking | CONSOLIDATED |
| MT12-082 | Stable tie-break. | scoring_ranking | CONSOLIDATED |
| MT12-083 | Advisory and MicroTwin rankings agree. | scoring_ranking | CONSOLIDATED |
| MT12-084 | Advisory and MicroTwin rankings disagree. | scoring_ranking | CONSOLIDATED |
| MT12-085 | Disagreement reported. | scoring_ranking | CONSOLIDATED |
| MT12-086 | Unqualified model prevents ranking. | scoring_ranking | CONSOLIDATED |
| MT12-087 | get_microtwin_status. | mcp_llm_policy | CONSOLIDATED |
| MT12-088 | get_microtwin_validation. | mcp_llm_policy | CONSOLIDATED |
| MT12-089 | evaluate persisted candidate. | mcp_llm_policy | CONSOLIDATED |
| MT12-090 | Unknown plan rejected. | mcp_llm_policy | CONSOLIDATED |
| MT12-091 | compare rollouts. | mcp_llm_policy | CONSOLIDATED |
| MT12-092 | bounded rollout response. | mcp_llm_policy | CONSOLIDATED |
| MT12-093 | rank all candidates. | mcp_llm_policy | CONSOLIDATED |
| MT12-094 | training tool unavailable through MCP. | mcp_llm_policy | CONSOLIDATED |
| MT12-095 | propose_guarded_control remains denied. | mcp_llm_policy | CONSOLIDATED |
| MT12-096 | Mock LLM explains validation. | mcp_llm_policy | CONSOLIDATED |
| MT12-097 | Mock LLM recommends ranked candidate. | mcp_llm_policy | CONSOLIDATED |
| MT12-098 | Invented rollout ID blocked. | mcp_llm_policy | CONSOLIDATED |
| MT12-099 | Modified score blocked. | mcp_llm_policy | CONSOLIDATED |
| MT12-100 | False EnergyPlus-result claim blocked. | mcp_llm_policy | CONSOLIDATED |
| MT12-101 | Verified-savings claim blocked. | mcp_llm_policy | CONSOLIDATED |
| MT12-102 | Physical-execution claim blocked. | mcp_llm_policy | CONSOLIDATED |
| MT12-103 | Exact replay. | persistence_replay | CONSOLIDATED |
| MT12-104 | Repeat complete suite. | persistence_replay | CONSOLIDATED |
| MT12-105 | Zero writes. | persistence_replay | CONSOLIDATED |
