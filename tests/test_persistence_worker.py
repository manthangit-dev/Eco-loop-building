from pathlib import Path

from src.storage.persistence_worker import StatePersistenceWorker
from src.storage.queries import open_read_only

from tests.state_helpers import completion, metadata, sample_state, with_sequence


def test_worker_drains_bounded_queue_and_finalises_run(tmp_path: Path) -> None:
    database = tmp_path / "state.db"
    worker = StatePersistenceWorker(
        database,
        tmp_path,
        metadata(expected=3),
        queue_capacity=2,
        batch_size=2,
        enqueue_timeout_seconds=1,
    )
    worker.start()
    state = sample_state()
    for sequence in range(1, 4):
        worker.enqueue(with_sequence(state, sequence))
    worker.set_completion(completion(count=3))
    worker.stop()
    stats = worker.statistics()
    assert stats["persisted_count"] == 3
    assert stats["final_drained"] is True
    with open_read_only(database) as connection:
        run = connection.execute("SELECT * FROM simulation_runs").fetchone()
        assert run["persisted_snapshot_count"] == 3
        assert run["queue_drained"] == 1
