# Thermal Bank

Module 15 preserves the zero-transaction result and states RTFU is not energy.

The Module 13 Thermal Bank is a deterministic advisory accounting metaphor expressed in relative thermal fairness units (RTFU). It is not a battery, does not store heat or electricity, and its balance must never be reported as kWh.

`config/thermal_bank.yaml` defines a zero opening balance, zero-overdraft policy, limits, decay, expiry, uncertainty reserve, and protected-event reserve. A candidate plan can deposit or withdraw only through the deterministic evaluator. Non-finite, negative, overdrawn, and over-limit states fail closed. The LLM and MCP clients have no direct balance-mutation tool.

Transactions and plan evaluations are persisted in additive database schema 8. The current demonstration produces no deposits or withdrawals because its protected comfort conditions do not establish eligible surplus credit. This zero activity is an honest evaluated result, not missing data.

Run `python scripts/evaluate_thermal_bank.py` and `python scripts/inspect_thermal_bank.py` for reproducible inspection.

Thermal Bank balances remain advisory during Module 14. They cannot create execution authority or bypass debt, approval, live-state, scheduling, or Module 8 validation.
