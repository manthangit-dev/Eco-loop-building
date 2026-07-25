# ThermoLedger AI — Repository Instructions

## Scope and sequencing

- Work on only the requested module. Read `README.md`, `config/project.yaml`, and relevant documents in `docs/` before editing.
- Never jump ahead to later modules. Stop and report missing prerequisites clearly.
- Do not fabricate simulation outputs, savings, benchmark results, or test outcomes. Only report a test as passed when its command was executed.

## Engineering rules

- Use Python 3.12-compatible syntax and type hints for public functions. Prefer small, focused modules.
- Use Pydantic models for structured external and LLM data.
- Keep EnergyPlus-specific logic separate from business logic; keep LLM reasoning separate from deterministic safety validation.
- An LLM may propose actions, but must never directly control EnergyPlus. Route every future action through a safety guard and retain a deterministic fallback that works without the LLM.
- Never hard-code installation paths; read them from configuration or environment variables. Keep Windows and WSL paths configurable.
- Preserve original IDF files and create derived copies for changes.
- Add or update tests whenever functional code is introduced. Avoid dependencies without a clear reason.

## Repository hygiene

- Never commit `.env` files, secrets, local databases, generated EnergyPlus outputs, or downloaded LLM models.
- Do not perform destructive Git operations. Create a Git checkpoint before a major refactor when Git is available.
- End tasks by explaining changed files and verification commands.

## Definition of done for coding modules

1. The requested scope is implemented.
2. Relevant validation or tests are executed.
3. Results are reported honestly.
4. Documentation affected by the change is updated.
5. No unrelated module is implemented.
