from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from src.energyplus.api_loader import load_energyplus_api, resolve_energyplus_home


class FakeHandle:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True

    def __enter__(self) -> FakeHandle:
        return self

    def __exit__(self, *_args: Any) -> None:
        self.close()


def _installation(tmp_path: Path) -> tuple[Path, Path]:
    home = tmp_path / "EnergyPlus"
    (home / "pyenergyplus").mkdir(parents=True)
    library = home / "EnergyPlusAPI.dll"
    library.write_bytes(b"dll")
    return home, library


def test_missing_energyplus_home(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="missing"):
        resolve_energyplus_home(tmp_path, {})


def test_missing_pyenergyplus_directory(tmp_path: Path) -> None:
    home = tmp_path / "EnergyPlus"
    home.mkdir()
    with pytest.raises(RuntimeError, match="pyenergyplus"):
        resolve_energyplus_home(tmp_path, {"ENERGYPLUS_HOME": str(home)})


def test_wrong_energyplus_version(tmp_path: Path) -> None:
    home, library = _installation(tmp_path)
    fake = SimpleNamespace(api=SimpleNamespace(_name=str(library)), api_version=lambda: "0.2")
    with pytest.raises(RuntimeError, match="26.1"):
        load_energyplus_api(
            tmp_path,
            {"ENERGYPLUS_HOME": str(home)},
            api_factory=lambda: fake,
            dll_adder=lambda _path: FakeHandle(),
            version_detector=lambda _home: (_ for _ in ()).throw(
                RuntimeError("EnergyPlus 26.1 is required")
            ),
        )


def test_successful_mocked_api_import(tmp_path: Path) -> None:
    home, library = _installation(tmp_path)
    fake = SimpleNamespace(api=SimpleNamespace(_name=str(library)), api_version=lambda: "0.2")
    loaded = load_energyplus_api(
        tmp_path,
        {"ENERGYPLUS_HOME": str(home)},
        api_factory=lambda: fake,
        dll_adder=lambda _path: FakeHandle(),
        version_detector=lambda _home: "EnergyPlus, Version 26.1.0",
    )
    assert loaded.api is fake
    assert loaded.api_version == "0.2"
    loaded.close()


def test_api_library_path_reporting(tmp_path: Path) -> None:
    home, library = _installation(tmp_path)
    fake = SimpleNamespace(api=SimpleNamespace(_name=str(library)), api_version=lambda: "0.2")
    loaded = load_energyplus_api(
        tmp_path,
        {"ENERGYPLUS_HOME": str(home)},
        api_factory=lambda: fake,
        dll_adder=lambda _path: FakeHandle(),
        version_detector=lambda _home: "26.1",
    )
    assert loaded.api_library_path == library.resolve()
    loaded.close()


def test_dll_directory_handle_is_retained_and_closed(tmp_path: Path) -> None:
    home, library = _installation(tmp_path)
    handle = FakeHandle()
    fake = SimpleNamespace(api=SimpleNamespace(_name=str(library)), api_version=lambda: "0.2")
    loaded = load_energyplus_api(
        tmp_path,
        {"ENERGYPLUS_HOME": str(home)},
        api_factory=lambda: fake,
        dll_adder=lambda _path: handle,
        version_detector=lambda _home: "26.1",
    )
    assert loaded.dll_directory_handle is handle
    loaded.close()
    assert handle.closed
