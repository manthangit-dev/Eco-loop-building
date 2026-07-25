from pathlib import Path

from src.energyplus.callbacks import CallbackCollector


def _collector(tmp_path: Path, stored: int = 2, length: int = 10) -> CallbackCollector:
    return CallbackCollector(tmp_path / "messages.log", stored, length)


def test_progress_event_collection(tmp_path: Path) -> None:
    collector = _collector(tmp_path)
    collector.progress_callback()(42)
    assert collector.progress_events[0]["progress"] == 42


def test_invalid_progress_is_contained(tmp_path: Path) -> None:
    collector = _collector(tmp_path)
    collector.progress_callback()(101)
    assert collector.errors


def test_message_bytes_and_invalid_utf8(tmp_path: Path) -> None:
    collector = _collector(tmp_path)
    collector.message_callback()(b"hello\xff")
    assert collector.messages == ["hello\ufffd"]


def test_message_truncation_and_memory_limit(tmp_path: Path) -> None:
    collector = _collector(tmp_path, stored=1, length=3)
    callback = collector.message_callback()
    callback(b"abcdef")
    callback(b"second")
    assert collector.message_count == 2
    assert collector.messages == ["abc"]
    assert collector.truncated_message_count == 2


def test_callback_log_writing(tmp_path: Path) -> None:
    collector = _collector(tmp_path)
    collector.message_callback()(b"logged")
    assert "logged" in collector.log_path.read_text(encoding="utf-8")


def test_environment_and_warmup_counters(tmp_path: Path) -> None:
    collector = _collector(tmp_path)
    collector.begin_environment_callback()(object())
    collector.warmup_complete_callback()(object())
    assert collector.environment_start_count == 1
    assert collector.warmup_complete_count == 1


def test_callback_exception_containment(tmp_path: Path) -> None:
    collector = _collector(tmp_path)
    collector.log_path.mkdir()
    collector.message_callback()(b"cannot write")
    assert collector.errors

