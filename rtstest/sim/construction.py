"""Construction: placing building sites and the worker's ``Build`` behaviour.

SC/WC style: one worker walks next to the site, places and pays for the
building on arrival (``start_construction``), then stays and advances it
with ``Building.construct``. A second worker sent to the same building gives
up while the first is still building. Package-internal; outside ``sim`` use
``Game.can_place``, ``Game.order_build`` and ``Game.order_resume``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from rtstest.sim.entities import point_rect_distance
from rtstest.sim.orders import Build, Move
from rtstest.sim.services import free_cell_near
from rtstest.world import Cell, find_path, find_path_adjacent, find_stand_cell

if TYPE_CHECKING:
    from rtstest.sim.buildings import Building, BuildingType
    from rtstest.sim.game import Game
    from rtstest.sim.units import Unit

__all__ = ["footprint", "can_place", "start_construction", "BuildBehaviour"]

BUILD_RANGE = 1.0


def footprint(btype: BuildingType, cell: Cell) -> list[Cell]:
    """Cells a building of ``btype`` with top-left ``cell`` would cover."""
    w, h = btype.size
    return [(cell[0] + dx, cell[1] + dy) for dy in range(h) for dx in range(w)]


def can_place(game: Game, btype: BuildingType, cell: Cell, owner: int) -> bool:
    """Whether ``owner`` may place ``btype`` here.

    Every cell must be passable and either unreserved or reserved by one of
    the owner's own idle or moving units (which will be moved aside).
    """
    for c in footprint(btype, cell):
        if not game.grid.is_passable(c):
            return False
        holder = game.units.get(game.grid.reserved_by(c))
        if holder is not None and (holder.owner != owner
                                   or not (holder.order is None
                                           or isinstance(holder.order, Move))):
            return False
    return True


def start_construction(game: Game, worker: Unit, btype: BuildingType,
                       cell: Cell) -> Building | None:
    """Pay for and place an unfinished building; None if blocked or unaffordable.

    Units standing on the site are moved to free cells next to it.
    """
    player = game.players[worker.owner]
    if player.resources < btype.cost or not can_place(game, btype, cell, worker.owner):
        return None
    cells = set(footprint(btype, cell))
    for u in game.units.values():
        if u.reserved in cells:
            u.release_reservation()
    building = game.place_building(btype, worker.owner, cell, complete=False)
    if building is None:
        return None
    player.resources -= btype.cost
    for u in game.units.values():
        if u.cell in cells:
            free = free_cell_near(game, cells)
            if free is not None:
                u.relocate(free)
    return building


def _is_building(game: Game, uid: int | None, building_id: int, other: Unit) -> bool:
    """Whether unit ``uid`` (not ``other``) is currently constructing the building."""
    unit = game.units.get(uid)
    return (unit is not None and unit is not other and isinstance(unit.order, Build)
            and unit.order.building_id == building_id)


class BuildBehaviour:
    """``Unit`` mixin: the ``Build`` order."""

    def _build(self, game: Game, dt: float) -> None:
        """Walk next to the site, start construction on arrival, then keep building.

        Only one worker builds a building: another worker that arrives while
        the current builder is still building gives up.
        """
        order = self.order
        building = None
        if order.building_id is not None:
            building = game.buildings.get(order.building_id)
            if building is None or building.complete:
                self.set_order(None)
                return
            cells = building.cells()
        else:
            cells = footprint(order.btype, order.cell)
        x0, y0 = cells[0]
        x1, y1 = cells[-1]
        if point_rect_distance(self.x, self.y, (x0, y0, x1 + 1, y1 + 1)) > BUILD_RANGE:
            if not self.path:
                stand = find_stand_cell(self._grid, self.cell, cells, self.id, 1, 2)
                if stand is not None and self._reserve(stand):
                    path = find_path(self._grid, self.cell, stand)
                else:
                    path = find_path_adjacent(self._grid, self.cell, cells)
                if path is None:
                    self.set_order(None)
                    return
                self.path = path or [self.cell]
            self._step(game, dt)
            return
        self.path = []
        if building is None:
            building = start_construction(game, self, order.btype, order.cell)
            if building is None:
                self.set_order(None)
                return
            order.building_id = building.id
        if not _is_building(game, building.builder, building.id, self):
            building.builder = self.id
        if building.builder != self.id:
            self.set_order(None)
            return
        if self.reserved != self.cell:
            self._reserve(self.cell)
        if building.construct(dt):
            self.set_order(None)
