from dataclasses import dataclass

@dataclass(frozen=True)
class Exercise:
    id: str
    name: str
    kind: str

@dataclass(frozen=True)
class Slot:
    id: str
    exercise: Exercise
    legacy_index: int

@dataclass(frozen=True)
class Measurements:
    weight: float | None = None
    reps: int | None = None
    duration_seconds: float | None = None

@dataclass(frozen=True)
class Snapshot:
    id: str
    status: str
    phase: str
    revision: int
    slots: tuple[Slot, ...]
    order: tuple[str, ...]
    current_slot_id: str | None
    set_index: int
    draft: Measurements
    set_elapsed_ms: int
    notice: str | None
