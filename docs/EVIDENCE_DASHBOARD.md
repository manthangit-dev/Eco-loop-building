# Read-only evidence dashboard

Module 15 presents persisted Modules 1–14A evidence through a versioned snapshot, a
loopback-only Python standard-library HTTP server, and local HTML/CSS/JavaScript. It does
not plan, approve, execute, write to SQLite, call MCP, start EnergyPlus, or require Ollama.

The evidence registry records artifact-relative sources, checksums, fingerprints, schema,
validation state, labels, and limitations. Each metric records its source IDs, unit,
precision, direct/calculated method, limitations, and claim classification. Startup refuses
missing, stale, checksum-mismatched, or incompatible mandatory evidence.

The dashboard contains overview, module matrix, planning, MicroTwin, Comfort Ledger,
Thermal Bank, approval/execution, native/live comparison, aligned reconciliation, safety,
provenance, and limitations views. Canvas charts use bounded backend-prepared data. The
historical January/July comparison is separated as invalid evidence; the July 19 result is
labelled short-horizon and its electricity increase is explicit.

Security is appropriate for a local demo, not production hosting: fixed `127.0.0.1` bind,
GET/HEAD only, structured 405 responses, fixed route registry, bounded pagination, local
assets, CSP, frame denial, `nosniff`, no CORS wildcard, no directory listing, and no upload,
SQL, shell, approval, or execution endpoint.

Start it with:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_evidence_dashboard.ps1
```

The persistent banner states simulation-only, read-only, annual savings not established,
real-world improvement not established, real-building control not implemented, and the
physical control tool disabled.
