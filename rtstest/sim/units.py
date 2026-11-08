"""Units: the ``Unit`` entity, order dispatch, movement and its reserved cell.

A unit stands at a float position in cell units (the centre of cell
``(x, y)`` is ``(x + 0.5, y + 0.5)``). Each tick ``Unit.update`` advances
its current order (see ``orders``). The behaviour for each order lives in
mixins: ``combat`` (idle scanning, ``Attack``, ``AttackMove``),
``gathering`` (``Gather``) and ``construction`` (``Build``). This module
keeps what they share: following paths and the single reserved cell.

Units reserve the cell they intend to stop on (``Grid.reserve``): a move
destination, a mining spot, a cell in range of an attack target, or a
building site's side. A unit holds at most one reservation; it is released
when the order changes and when the unit dies (``release_reservation``).
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from rtstest.sim.combat import CombatBehaviour
from rtstest.sim.construction import BuildBehaviour
from rtstest.sim.entities import point_rect_distance
from rtstest.sim.gathering import GatheringBehaviour
from rtstest.sim.orders import AttackMove, Build, Gather, Move, Order
from rtstest.sim.unit_types import REPATH_INTERVAL, UnitType
from rtstest.world import Cell, Grid, find_path, find_path_adjacent, find_stand_cell

if TYPE_CHECKING:
    from rtstest.sim.entities import Entity
    from rtstest.sim.game import Game

__all__ = ["Unit"]

MOVE_MAX_RING = 4


class Unit(CombatBehaviour, GatheringBehaviour, BuildBehaviour):
    """A mobile entity owned by a player or by the hazard; implements ``Entity``.

    Public attributes (read-only outside ``sim``): ``id``, ``type``,
    ``owner``, ``x``, ``y`` (float position in cell units), ``hp``,
    ``max_hp``, ``damage``, ``carrying`` (resources held), ``order`` (the
    current ``Order``). Properties: ``cell``, ``alive``. Methods:
    ``distance_to``, ``set_order``.

    Package-internal (used by other ``sim`` modules): ``path`` (cells still
    to walk), ``reserved`` (reserved stopping cell), ``last_attacker``,
    ``update``, ``release_reservation``, ``relocate``.
    """

    def __init__(self, uid: int, utype: UnitType, owner: int, cell: Cell, grid: Grid,
                 scale: float = 1.0) -> None:
        self.id = uid
        self._grid = grid
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
        self._cooldown = 0.0
        self._repath_timer = 0.0
        self._scan_timer = 0.0
        self._work_timer = 0.0
        self.last_attacker: int | None = None
        self.reserved: Cell | None = None
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
        """Replace the current order, forget the old path and release the reservation."""
        self.release_reservation()
        self.order = order
        self.path = []
        self._path_key = None
        self._work_timer = 0.0

    def release_reservation(self) -> None:
        """Give up the reserved stopping cell, if any."""
        if self.reserved is not None:
            self._grid.unreserve(self.reserved, self.id)
            self.reserved = None

    def relocate(self, cell: Cell) -> None:
        """Put the unit on the centre of ``cell`` at once and drop its path.

        Used when a building is placed on top of the unit.
        """
        self.x, self.y = cell[0] + 0.5, cell[1] + 0.5
        self.path = []
        self._path_key = None

    def update(self, game: Game, dt: float) -> None:
        """Advance the current order by ``dt`` seconds."""
        self._cooldown = max(0.0, self._cooldown - dt)
        self._repath_timer -= dt
        order = self.order
        if order is None:
            self._idle(game, dt)
        elif isinstance(order, Move):
            self._move(game, dt)
        elif isinstance(order, Gather):
            self._gather(game, dt)
        elif isinstance(order, AttackMove):
            self._attack_move(game, dt)
        elif isinstance(order, Build):
            self._build(game, dt)
        else:
            self._attack(game, dt)

    def _reserve(self, cell: Cell) -> bool:
        """Move our single reservation to ``cell``; False if another unit holds it."""
        if self.reserved == cell:
            return True
        if not self._grid.can_stand(cell, self.id):
            return False
        self.release_reservation()
        self._grid.reserve(cell, self.id)
        self.reserved = cell
        return True

    def _claim_destination(self, order: Move | AttackMove) -> None:
        """Reserve the nearest free cell around the order's target and retarget to it."""
        order.claimed = True
        stand = find_stand_cell(self._grid, self.cell, [order.target], self.id, 0, MOVE_MAX_RING)
        if stand is not None and self._reserve(stand):
            if stand != order.target:
                order.target = stand
                self.path = []

    def _move(self, game: Game, dt: float) -> None:
        if not self.order.claimed:
            self._claim_destination(self.order)
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

    def _approach(self, game: Game, cells: list[Cell], dt: float) -> None:
        """Walk towards a cell next to ``cells``, repathing if they moved."""
        key = tuple(cells)
        if not self.path or (key != self._path_key and self._repath_timer <= 0):
            self._repath_timer = REPATH_INTERVAL
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
