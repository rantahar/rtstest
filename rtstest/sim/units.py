"""Units: unit types, orders and per-tick unit behaviour.

A unit stands at a float position in cell units (the centre of cell
``(x, y)`` is ``(x + 0.5, y + 0.5)``). Each tick ``Unit.update`` advances its
current order: ``Move``, ``Gather``, ``Attack`` or ``AttackMove``. Idle combat units attack
hostiles in sight (as decided by ``Game.nearest_hostile``); workers only
act on orders.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, Union

from rtstest.world.grid import Cell, Terrain, chebyshev
from rtstest.world.pathfinding import find_path, find_path_adjacent

if TYPE_CHECKING:
    from rtstest.sim.game import Entity, Game

REPATH_INTERVAL = 0.5
SCAN_INTERVAL = 0.5
GATHER_TIME = 0.5
GATHER_SEARCH_RADIUS = 10
DEPOSIT_RANGE = 1.0


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


@dataclass
class Move:
    """Walk to a cell."""

    target: Cell


@dataclass
class Gather:
    """Harvest a resource cell and carry full loads to the nearest own building."""

    resource: Cell
    returning: bool = False


@dataclass
class Attack:
    """Chase and hit the entity with this id until it is gone."""

    target_id: int


@dataclass
class AttackMove:
    """Walk to a cell, fighting any hostile met on the way, then carry on."""

    target: Cell
    engaged: int | None = None


Order = Union[Move, Gather, Attack, AttackMove, None]


def point_rect_distance(px: float, py: float,
                        bounds: tuple[float, float, float, float]) -> float:
    """Distance from a point to an axis-aligned rectangle (0 inside it)."""
    x0, y0, x1, y1 = bounds
    return math.hypot(max(x0 - px, 0.0, px - x1), max(y0 - py, 0.0, py - y1))


class Unit:
    """A mobile entity owned by a player or by the hazard."""

    def __init__(self, uid: int, utype: UnitType, owner: int, cell: Cell,
                 scale: float = 1.0) -> None:
        self.id = uid
        self.type = utype
        self.owner = owner
        self.x = cell[0] + 0.5
        self.y = cell[1] + 0.5
        self.max_hp = round(utype.max_hp * scale)
        self.hp = float(self.max_hp)
        self.damage = utype.damage * scale
        self.order: Order = None
        self.path: list[Cell] = []
        self.carrying = 0
        self.cooldown = 0.0
        self.repath_timer = 0.0
        self.scan_timer = 0.0
        self.work_timer = 0.0
        self.last_attacker: int | None = None
        self._path_key: tuple[Cell, ...] | None = None

    @property
    def cell(self) -> Cell:
        """The cell the unit stands in."""
        return (math.floor(self.x), math.floor(self.y))

    @property
    def alive(self) -> bool:
        return self.hp > 0

    def cells(self) -> list[Cell]:
        """Footprint cells (just the unit's own cell)."""
        return [self.cell]

    def bounds(self) -> tuple[float, float, float, float]:
        """Footprint rectangle ``(x0, y0, x1, y1)`` in cell units."""
        return (self.x - 0.5, self.y - 0.5, self.x + 0.5, self.y + 0.5)

    def distance_to(self, entity: Entity) -> float:
        """Distance from this unit's centre to another entity's footprint."""
        return point_rect_distance(self.x, self.y, entity.bounds())

    def take_damage(self, amount: float, attacker: Entity | None = None) -> None:
        """Lose hp and remember who hit us, so idle units can retaliate."""
        self.hp -= amount
        if attacker is not None:
            self.last_attacker = attacker.id

    def set_order(self, order: Order) -> None:
        """Replace the current order and forget the old path."""
        self.order = order
        self.path = []
        self._path_key = None
        self.work_timer = 0.0

    def update(self, game: Game, dt: float) -> None:
        """Advance the current order by ``dt`` seconds."""
        self.cooldown = max(0.0, self.cooldown - dt)
        self.repath_timer -= dt
        order = self.order
        if order is None:
            self._idle(game, dt)
        elif isinstance(order, Move):
            self._move(game, dt)
        elif isinstance(order, Gather):
            self._gather(game, dt)
        elif isinstance(order, AttackMove):
            self._attack_move(game, dt)
        else:
            self._attack(game, dt)

    def _idle(self, game: Game, dt: float) -> None:
        """Combat units periodically look for something hostile to attack."""
        self.scan_timer -= dt
        if self.scan_timer > 0 or self.type.gather_capacity:
            return
        self.scan_timer = SCAN_INTERVAL
        enemy = game.nearest_hostile(self)
        if enemy is not None:
            self.set_order(Attack(enemy.id))

    def _move(self, game: Game, dt: float) -> None:
        self._walk_to(game, self.order.target, dt)

    def _walk_to(self, game: Game, target: Cell, dt: float) -> None:
        """Walk to a cell; the order ends on arrival or when it is unreachable."""
        if not self.path:
            if self.cell == target:
                self.order = None
                return
            path = find_path(game.grid, self.cell, target)
            if not path:
                self.order = None
                return
            self.path = path
        self._step(game, dt)

    def _attack(self, game: Game, dt: float) -> None:
        target = game.entity(self.order.target_id)
        if target is None or not target.alive:
            self.set_order(None)
            return
        self._engage(game, target, dt)

    def _attack_move(self, game: Game, dt: float) -> None:
        order = self.order
        target = game.entity(order.engaged) if order.engaged is not None else None
        if target is None or not target.alive:
            if order.engaged is not None:
                order.engaged = None
                self.path = []
                self._path_key = None
            self.scan_timer -= dt
            if self.scan_timer <= 0:
                self.scan_timer = SCAN_INTERVAL
                target = game.nearest_hostile(self)
                if target is not None:
                    order.engaged = target.id
                    self.path = []
                    self._path_key = None
        if target is not None:
            self._engage(game, target, dt)
        else:
            self._walk_to(game, order.target, dt)

    def _engage(self, game: Game, target: Entity, dt: float) -> None:
        """Hit the target when in range, otherwise close in on it."""
        if self.distance_to(target) <= self.type.attack_range:
            self.path = []
            self._path_key = None
            if self.cooldown <= 0:
                target.take_damage(self.damage, self)
                self.cooldown = self.type.attack_cooldown
            return
        self._approach(game, target.cells(), dt)

    def _gather(self, game: Game, dt: float) -> None:
        order = self.order
        grid = game.grid
        if not order.returning and grid.terrain_at(order.resource) != Terrain.RESOURCE:
            nxt = game.nearest_resource(self.cell, GATHER_SEARCH_RADIUS)
            if nxt is not None:
                order.resource = nxt
                self.path = []
            elif self.carrying:
                order.returning = True
                self.path = []
            else:
                self.set_order(None)
                return
        if order.returning:
            self._return_load(game, dt)
            return
        if chebyshev(self.cell, order.resource) <= 1:
            self.path = []
            self.work_timer += dt
            if self.work_timer >= GATHER_TIME:
                self.work_timer = 0.0
                self.carrying += grid.take_resource(order.resource, 1)
                if self.carrying >= self.type.gather_capacity:
                    order.returning = True
            return
        self._approach(game, [order.resource], dt)

    def _return_load(self, game: Game, dt: float) -> None:
        """Walk to the nearest own building and deposit what we carry."""
        base = game.nearest_base(self.owner, self.x, self.y)
        if base is None:
            self.set_order(None)
            return
        if self.distance_to(base) <= DEPOSIT_RANGE:
            game.players[self.owner].resources += self.carrying
            self.carrying = 0
            self.order.returning = False
            self.path = []
            self._path_key = None
            return
        self._approach(game, base.cells(), dt)

    def _approach(self, game: Game, cells: list[Cell], dt: float) -> None:
        """Walk towards a cell next to ``cells``, repathing if they moved."""
        key = tuple(cells)
        if not self.path or (key != self._path_key and self.repath_timer <= 0):
            self.repath_timer = REPATH_INTERVAL
            path = find_path_adjacent(game.grid, self.cell, cells)
            if path is None:
                self.set_order(None)
                return
            self.path = path or [self.cell]
            self._path_key = key
        self._step(game, dt)

    def _step(self, game: Game, dt: float) -> None:
        """Move along the path towards cell centres at the unit's speed."""
        budget = self.type.speed * dt
        while self.path and budget > 0:
            nxt = self.path[0]
            if nxt != self.cell and not game.grid.is_passable(nxt):
                self.path = []
                return
            tx, ty = nxt[0] + 0.5, nxt[1] + 0.5
            dx, dy = tx - self.x, ty - self.y
            dist = math.hypot(dx, dy)
            if dist <= budget:
                self.x, self.y = tx, ty
                budget -= dist
                self.path.pop(0)
            else:
                self.x += dx / dist * budget
                self.y += dy / dist * budget
                budget = 0
