"""Per-zone deterministic controller memory."""

from dataclasses import replace

from src.control.models import ControllerSnapshot, ZoneControllerMemory


class ControllerMemory:
    def __init__(self, run_id: str) -> None:
        self.run_id = run_id
        self._zones: dict[str, ZoneControllerMemory] = {}

    def get(self, zone_id: str) -> ZoneControllerMemory:
        return self._zones.get(zone_id, ZoneControllerMemory(zone_id))

    def update(self, memory: ZoneControllerMemory) -> None:
        self._zones[memory.zone_id] = memory

    def reset(self, zone_id: str, sequence: int) -> ZoneControllerMemory:
        memory = replace(
            self.get(zone_id),
            active_command=False,
            last_command_setpoint=None,
            command_expiry_sequence=0,
            last_reset_sequence=sequence,
        )
        self.update(memory)
        return memory

    def snapshot(self, state_sequence: int) -> ControllerSnapshot:
        return ControllerSnapshot(
            self.run_id,
            state_sequence,
            tuple(self._zones[key] for key in sorted(self._zones)),
        )

    def restore(self, snapshot: ControllerSnapshot) -> None:
        if snapshot.run_id != self.run_id:
            raise ValueError("Cannot restore memory from another run.")
        self._zones = {item.zone_id: item for item in snapshot.memories}
