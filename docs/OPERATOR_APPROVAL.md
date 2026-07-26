# Local Operator Approval

Module 14A approvals bind the exact calendar and derived IDF and become `CONSUMED` after live use.

An approval is an immutable local artifact, not cryptographic authorisation. It binds the repository instance, simulation-only flag, execution mode, exact plan/context/rollout/ledger/model fingerprints, canonical actuator, zone, units, action values/count, write/reset limits, environment, expiry, and source/baseline/EPW checksums. Creation dynamically resolves trusted values; operators do not copy fingerprints manually.

The operator must explicitly confirm: “I approve simulation-only EnergyPlus actuation for the exact bound plan. This does not approve real-building or hardware control.” Missing confirmation, missing simulation-only scope, expiry, reuse, mode mismatch, changed artifact, invalid limits, or changed eligibility keeps execution disarmed. Successful terminal execution consumes the approval once.

Example tested creation pattern:

```powershell
.\.venv\Scripts\python.exe scripts\create_execution_approval.py --plan-id 3ae11d4aa482502d4e1ff741ef49f007a22eb4a1067236651956d0defa113dae --mode LIVE_SHORT_HORIZON --expires-in-minutes 30 --maximum-writes 20 --maximum-resets 2 --simulation-only --confirm --output outputs\module14\live_approval.json --json
```
