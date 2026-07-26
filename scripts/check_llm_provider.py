"""Report bounded local provider health without network fallback."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.llm.config import load_llm_settings
from src.llm.local_provider import LocalOpenSourceProvider


def main() -> int:
    argparse.ArgumentParser(description=__doc__).parse_args()
    settings = load_llm_settings(Path("config/llm_supervisor.yaml"))
    provider = LocalOpenSourceProvider(settings)
    print(json.dumps({"provider": provider.name, "healthy": provider.health_check()}))
    provider.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
