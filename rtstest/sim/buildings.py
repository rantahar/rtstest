"""Buildings: rectangular grid footprints that store resources and train units.

A building's ``cell`` is its top-left footprint cell. Training is paid up
front by ``Game.train``; the building then spends ``train_time`` per queued
unit and spawns it on a free cell next to its footprint. If the building has
a rally point, each new unit's first order goes there: gather when the rally
point is a resource cell and the unit can gather, otherwise move.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from rtstest.sim.units import SOLDIER, WORKER, UnitType
from rtstest.world.grid import Cell

if TYPE_CHECKING:
    from rtstest.sim.game import Entity, Game

MAX_QUEUE = 5


@dataclass(frozen=True)
class BuildingType:
    """Stats shared by buildings of one kind; ``name`` is also the sprite name."""

    name: str
    max_hp: int
    size: tuple[int, int]
    trains: tuple[UnitType, ...] = ()


BASE = BuildingType("base", 600, (3, 3), (WORKER, SOLDIER))


class Building:
    """A static entity on the grid, owned by a player."""

    def __init__(self, bid: int, btype: BuildingType, owner: int, cell: Cell) -> None:
        self.id = bid
        self.type = btype
        self.owner = owner
        self.cell = cell
        self.hp = float(btype.max_hp)
        self.max_hp = btype.max_hp
        self.queue: list[UnitType] = []
        self.progress = 0.0
        self.rally: Cell | None = None

    @property
    def alive(self) -> bool:
        return self.hp > 0

    @property
    def center(self) -> tuple[float, float]:
        """Centre of the footprint in cell units."""
        w, h = self.type.size
        return (self.cell[0] + w / 2, self.cell[1] + h / 2)

    def cells(self) -> list[Cell]:
        """All footprint cells."""
        x0, y0 = self.cell
        w, h = self.type.size
        return [(x0 + dx, y0 + dy) for dy in range(h) for dx in range(w)]

    def bounds(self) -> tuple[float, float, float, float]:
        """Footprint rectangle ``(x0, y0, x1, y1)`` in cell units."""
        w, h = self.type.size
        return (self.cell[0], self.cell[1], self.cell[0] + w, self.cell[1] + h)

    def take_damage(self, amount: float, attacker: Entity | None = None) -> None:
        """Lose hp; buildings do not fight back."""
        self.hp -= amount

    def can_enqueue(self, utype: UnitType) -> bool:
        """Whether this building trains ``utype`` and has queue space."""
        return utype in self.type.trains and len(self.queue) < MAX_QUEUE

    def update(self, game: Game, dt: float) -> None:
        """Advance training; spawn the front unit when done and a cell is free.

        A spawned unit is sent to the rally point, if one is set.
        """
        if not self.queue:
            return
        self.progress += dt
        if self.progress < self.queue[0].train_time:
            return
        cell = game.free_cell_near(self.cells())
        if cell is not None:
            unit = game.spawn_unit(self.queue.pop(0), self.owner, cell)
            self.progress = 0.0
            if self.rally is not None:
                game.order_gather([unit.id], self.rally)
