# LLM trusted-field boundary

Run identity, environment identity, committed source-state identity and time,
decision/current sequence, validity interval, canonical actuator identity, units,
schema versions, safety context, and dry-run status are trusted system fields.
The model may suggest only a desired value, strategy, rationale, objective, and
explanation. Users provide the requested objective, zone, optional value, and
response detail.

For historical replay, a committed source state at sequence `N` creates a decision
at `N`, an immediately applicable command at `N+1`, and expiry at `N+2`. Simulation
time is derived deterministically from the recorded state/sequence, never from model
output or wall-clock time. This preserves future, stale, and expiry checks while
avoiding the former `command_from_future` error caused by evaluating an `N+1`
command at `N`.

Focused tests prove hostile model causal metadata is ignored, a valid request is
allowed, explicit future/stale/expired cases remain blocked, PLENUM-1 remains
rejected, and all checks are dry-run with zero physical writes.
