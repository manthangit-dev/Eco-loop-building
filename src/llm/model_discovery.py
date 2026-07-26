"""Deterministic local runtime and model discovery."""

import os
import shutil
from pathlib import Path

from src.llm.local_provider import LocalOpenSourceProvider
from src.llm.models import LocalModel


def runtime_installed() -> bool:
    local = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs/Ollama/ollama.exe"
    return shutil.which("ollama") is not None or local.is_file()


def select_model(models: tuple[LocalModel, ...]) -> LocalModel | None:
    compatible = sorted((item for item in models if item.compatible), key=lambda item: item.name)
    return compatible[0] if compatible else None


def discover(provider: LocalOpenSourceProvider) -> tuple[bool, tuple[LocalModel, ...]]:
    if not runtime_installed() or not provider.health_check():
        return False, ()
    return True, provider.list_local_models()
