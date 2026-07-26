"""Discover installed local-only model runtime and models."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.llm.config import load_llm_settings  # noqa: E402
from src.llm.local_provider import LocalOpenSourceProvider  # noqa: E402
from src.llm.model_discovery import discover, runtime_installed, select_model  # noqa: E402


def main() -> int:
    argparse.ArgumentParser(description=__doc__).parse_args()
    settings = load_llm_settings(Path("config/llm_supervisor.yaml"))
    provider = LocalOpenSourceProvider(settings)
    healthy, models = discover(provider)
    selected = select_model(models)
    report = {
        "runtime": "ollama",
        "runtime_installed": runtime_installed(),
        "healthy": healthy,
        "models": [item.model_dump(mode="json") for item in models],
        "selected_model": None if selected is None else selected.name,
        "endpoint": settings.endpoint,
        "model_acquisition_performed": False,
    }
    path = settings.output_root / "model_discovery.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
