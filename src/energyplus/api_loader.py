"""Safe loading of the EnergyPlus installation-provided Python API."""

from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from types import TracebackType
from typing import Any, Protocol


class DllHandle(Protocol):
    def close(self) -> None: ...

    def __enter__(self) -> DllHandle: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...


@dataclass
class LoadedAPI:
    api: Any
    energyplus_home: Path
    api_version: str
    api_library_path: Path
    energyplus_version: str
    dll_directory_handle: DllHandle | None = None

    def close(self) -> None:
        if self.dll_directory_handle is not None:
            self.dll_directory_handle.close()
            self.dll_directory_handle = None


def read_dotenv_value(path: Path, name: str) -> str | None:
    if not path.is_file():
        return None
    value: str | None = None
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, candidate = line.split("=", 1)
        if key.strip() == name:
            value = candidate.strip().strip("\"'")
    return value or None


def resolve_energyplus_home(
    root: Path, environ: Mapping[str, str] | None = None
) -> Path:
    env = environ if environ is not None else os.environ
    raw = env.get("ENERGYPLUS_HOME") or read_dotenv_value(root / ".env", "ENERGYPLUS_HOME")
    if not raw:
        raise RuntimeError("ENERGYPLUS_HOME is missing from the process and local .env.")
    path = Path(raw).expanduser().resolve()
    if not path.is_dir():
        raise RuntimeError(f"ENERGYPLUS_HOME does not exist: {path}")
    if not (path / "pyenergyplus").is_dir():
        raise RuntimeError(f"pyenergyplus directory is missing below {path}")
    return path


def _detect_version(home: Path) -> str:
    executable = home / ("energyplus.exe" if os.name == "nt" else "energyplus")
    if not executable.is_file():
        raise RuntimeError(f"EnergyPlus executable is missing: {executable}")
    completed = subprocess.run(
        [str(executable), "--version"],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    text = f"{completed.stdout}\n{completed.stderr}".strip()
    if completed.returncode != 0:
        raise RuntimeError(f"EnergyPlus version inspection failed: {text}")
    if "26.1" not in text:
        raise RuntimeError(f"EnergyPlus 26.1 is required; reported: {text}")
    return text.splitlines()[0]


def load_energyplus_api(
    root: Path,
    environ: Mapping[str, str] | None = None,
    api_factory: Callable[[], Any] | None = None,
    dll_adder: Callable[[str], DllHandle] | None = None,
    version_detector: Callable[[Path], str] | None = None,
) -> LoadedAPI:
    home = resolve_energyplus_home(root, environ)
    handle: DllHandle | None = None
    try:
        if os.name == "nt":
            add_directory = dll_adder or os.add_dll_directory
            handle = add_directory(str(home))
        if str(home) not in sys.path:
            sys.path.insert(0, str(home))
        if api_factory is None:
            try:
                from pyenergyplus.api import EnergyPlusAPI  # type: ignore[import-not-found]
            except (ImportError, OSError) as exc:
                raise RuntimeError(
                    f"Could not import the installed pyenergyplus API: {exc}"
                ) from exc
            api_factory = EnergyPlusAPI
        try:
            api = api_factory()
        except OSError as exc:
            raise RuntimeError(f"EnergyPlus API DLL loading failed: {exc}") from exc
        api_version = str(api.api_version())
        if not api_version:
            raise RuntimeError("EnergyPlus API version verification returned an empty value.")
        library_name = getattr(getattr(api, "api", None), "_name", None)
        if not library_name:
            raise RuntimeError("The loaded EnergyPlus API did not expose its DLL path.")
        library_path = Path(str(library_name)).resolve()
        if not library_path.is_file():
            raise RuntimeError(f"EnergyPlus API library is missing: {library_path}")
        return LoadedAPI(
            api=api,
            energyplus_home=home,
            api_version=api_version,
            api_library_path=library_path,
            energyplus_version=(version_detector or _detect_version)(home),
            dll_directory_handle=handle,
        )
    except (RuntimeError, ImportError, OSError, AttributeError, TypeError, ValueError):
        if handle is not None:
            handle.close()
        raise
