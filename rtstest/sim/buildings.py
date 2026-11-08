"""Buildings: rectangular grid footprints that train units; bases also store resources.

A building's ``cell`` is its top-left footprint cell. Buildings are
constructed SC/WC style: one worker stays next to the site while
``construct`` advances it; the building starts at ``START_HP_FRACTION`` of
its hp and gains hp as it is built. An unfinished building blocks its cells
and can be attacked, but trains nothing and takes no deposits.

Up to ``MAX_QUEUE`` units can be queued for free; a unit is paid for when
its training starts at the front of the queue, and the queue waits until the
owner can afford it. Training takes ``train_time``, then the unit spawns on a
free cell next to the footprint. Cancelling the front unit refunds it if it
was paid. If the building has a rally point, each new unit's first order goes
there: gather when the rally point is a resource cell and the unit can
gather, otherwise move.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from rtstest.sim.services import free_cell_near
from rtstest.sim.unit_types import SOLDIER, WORKER, UnitType
from rtstest.world import Cell

if TYPE_CHECKING:
    from rtstest.sim.entities import Entity
    from rtstest.sim.game import Game

__all__ = ["BuildingType", "BASE", "BARRACKS", "BUILDABLE", "MAX_QUEUE", "Building"]

MAX_QUEUE = 5
START_HP_FRACTION = 0.1


@dataclass(frozen=True)
class BuildingType:
    """Stats shared by buildings of one kind; ``name`` is also the sprite name."""

    name: str
    max_hp: int
    size: tuple[int, int]
    trains: tuple[UnitType, ...] = ()
    cost: int = 0
    build_time: float = 0.0
    stores_resources: bool = False


BASE = BuildingType("base", 600, (3, 3), (WORKER,), cost=400, build_time=60.0,
                    stores_resources=True)
BARRACKS = BuildingType("barracks", 400, (3, 3), (SOLDIER,), cost=150, build_time=30.0)
BUILDABLE = (BARRACKS,)


class Building:
    """A static entity on the grid, owned by a player; implements ``Entity``.

    Public attributes (read-only outside ``sim``): ``id``, ``type``,
    ``owner``, ``cell`` (top-left), ``hp``, ``max_hp``, ``complete``,
    ``queue`` (unit types waiting, front first), ``rally`` (cell or None).
    Properties: ``alive``, ``center``, ``build_fraction``,
    ``training_fraction``, ``waiting_for_resources``.

    Package-internal: ``builder`` (id of the worker constructing it),
    ``construct``, ``can_enqueue``, ``cancel``, ``update``.
    """

    def __init__(self, bid: int, btype: BuildingType, owner: int, cell: Cell,
                 complete: bool = True) -> None:
        self.id = bid
        self.type = btype
        self.owner = owner
        self.cell = cell
        self.max_hp = btype.max_hp
        self.complete = complete
        self.build_progress = btype.build_time if complete else 0.0
        self.builder: int | None = None
        self.hp = float(btype.max_hp) if complete else btype.max_hp * START_HP_FRACTION
        self.queue: list[UnitType] = []
        self._progress = 0.0
        self._paid = False
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

    @property
    def training_fraction(self) -> float:
        """Progress of the front unit's training from 0 to 1 (0 when idle or unpaid)."""
        if not self.queue or not self._paid:
            return 0.0
        return min(1.0, self._progress / self.queue[0].train_time)

    @property
    def waiting_for_resources(self) -> bool:
        """Whether the front unit is queued but not yet paid for."""
        return bool(self.queue) and self.complete and not self._paid

    @property
    def build_fraction(self) -> float:
        """Construction progress from 0 to 1."""
        if self.type.build_time <= 0:
            return 1.0
        return min(1.0, self.build_progress / self.type.build_time)

    def construct(self, dt: float) -> bool:
        """Advance construction by ``dt`` seconds of work; True when it completes."""
        if self.complete:
            return True
        before = self.build_fraction
        self.build_progress += dt
        gained = (self.build_fraction - before) * self.max_hp * (1 - START_HP_FRACTION)
        self.hp = min(float(self.max_hp), self.hp + gained)
        if self.build_progress >= self.type.build_time:
            self.complete = True
            self.builder = None
        return self.complete

    def can_enqueue(self, utype: UnitType) -> bool:
        """Whether this building is complete, trains ``utype`` and has queue space."""
        return self.complete and utype in self.type.trains and len(self.queue) < MAX_QUEUE

    def update(self, game: Game, dt: float) -> None:
        """Advance training; spawn the front unit when done and a cell is free.

        A spawned unit is sent to the rally point, if one is set.
        """
        if not self.complete or not self.queue:
            return
        front = self.queue[0]
        if not self._paid:
            player = game.players[self.owner]
            if player.resources < front.cost:
                return
            player.resources -= front.cost
            self._paid = True
        self._progress += dt
        if self._progress < front.train_time:
            return
        cell = free_cell_near(game, self.cells())
        if cell is not None:
            unit = game.spawn_unit(self.queue.pop(0), self.owner, cell)
            self._progress = 0.0
            self._paid = False
            if self.rally is not None:
                game.order_gather([unit.id], self.rally)

    def cancel(self, index: int) -> int:
        """Remove queue entry ``index``; return the refund (non-zero only for a paid front)."""
        if not 0 <= index < len(self.queue):
            return 0
        utype = self.queue.pop(index)
        if index != 0:
            return 0
        refund = utype.cost if self._paid else 0
        self._paid = False
        self._progress = 0.0
        return refund
