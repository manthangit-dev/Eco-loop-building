# Evidence package

`scripts/export_hackathon_evidence.py` creates a deterministic, bounded package from the
validated snapshot. It includes the snapshot, manifest, ten claim-bounded Markdown reports,
three chart CSV files, and a checksum manifest. The checksum manifest is not a signature.

The package excludes the raw SQLite database, absolute private paths, secrets, environment
files, prompts, model weights, Ollama files, and unbounded logs. Every report preserves the
simulation-only boundary, demand-model unavailability, RTFU proxy status, aligned
reconciliation limits, electricity increase, and absence of annual or real-world evidence.

```powershell
.\.venv\Scripts\python.exe scripts/export_hackathon_evidence.py --json
```
