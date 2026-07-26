# Module 15 design decision

## Decision

Use Python's standard-library `ThreadingHTTPServer` with a versioned, prebuilt evidence
snapshot and local HTML/CSS/JavaScript. No new web dependency or frontend build system is
introduced. The server binds only to `127.0.0.1`, serves a fixed route registry, reads one
validated snapshot, and has no reference to planning, approval, EnergyPlus, LLM, safety
writer, or mutable storage services.

## Read-only boundary

Only `GET` and `HEAD` are handled. `POST`, `PUT`, `PATCH`, and `DELETE` return structured
JSON `405` responses with `Allow: GET, HEAD`. There are no execution, approval creation,
upload, SQL, shell, rebuild, or arbitrary file routes. Snapshot creation and export are
explicit offline CLIs and cannot be triggered over HTTP.

## Evidence architecture

Validated Modules 1–14A artifacts are converted into typed `EvidenceSource` and
`EvidenceValue` records. Every displayed metric references source IDs, units, precision,
calculation method, limitations, and one of the seven required claim classifications. The
snapshot records source checksums and fingerprints; startup fails if a mandatory source is
missing or changed. The scientific database remains schema 10 and is opened read-only only
for validation metadata.

## Security and portability

All assets are repository-local. Responses include a local-only content security policy,
frame denial, `nosniff`, restrictive referrer policy, and no wildcard CORS. API arrays and
query limits are bounded. Ordinary responses and exports use repository-relative paths and
exclude databases, secrets, model weights, prompts, and machine-specific paths.

## Presentation boundary

The dashboard calls the July 19 result a short-horizon simulation result and explicitly
shows the electricity increase. Annual savings and real-world comfort improvement remain
`NOT_ESTABLISHED`; real-building control remains `NOT_IMPLEMENTED`; RTFU remains a relative
proxy. The January/July reconciliation is preserved only as historical invalid evidence.
