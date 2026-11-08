"""Unit types: the stats shared by all units of one kind, and shared unit timing.

No behaviour here, so ``buildings`` (what a building trains) and ``units``
can both depend on it without depending on each other.
"""

from dataclasses import dataclass

__all__ = ["UnitType", "WORKER", "SOLDIER", "CREEP", "REPATH_INTERVAL"]

REPATH_INTERVAL = 0.5


@dataclass(frozen=True)
class UnitType:
    """Stats shared by all units of one kind; ``name`` is also the sprite name.

    Speed is in cells per second; ranges are in cells, measured to the edge
    of the target's footprint.
    """

    name: str
    max_hp: int
    speed: float
    damage: float
    attack_range: float
    attack_cooldown: float
    sight: float
    cost: int
    train_time: float
    gather_capacity: int = 0


WORKER = UnitType("worker", 40, 2.5, 3, 1.2, 1.0, 5, 50, 5.0, gather_capacity=10)
SOLDIER = UnitType("soldier", 100, 2.2, 10, 1.2, 1.0, 6, 75, 8.0)
CREEP = UnitType("creep", 50, 1.8, 6, 1.2, 1.2, 8, 0, 0.0)
