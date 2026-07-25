from pathlib import Path

import pytest
import scripts.replay_sensor_states as replay_module


def test_replay_cli_forwards_limit(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    seen: list[tuple[Path, int | None]] = []

    def fake_replay(path: Path, limit: int | None) -> tuple[bool, Path]:
        seen.append((path, limit))
        return True, tmp_path / "summary.json"

    monkeypatch.setattr(replay_module, "replay", fake_replay)
    assert replay_module.main(["--limit", "2"]) == 0
    assert seen[0][1] == 2
