"""World services for units and buildings: target search, free cells, displacement.

Functions taking the ``Game`` that unit behaviours, buildings and the hazard
call while updating. Package-internal: UI and computer players use the
``Game`` lookups and commands instead.
"""

from __future__ import annotations

import math
from collections import deque
from collections.abc import Iterable
from typing import TYPE_CHECKING

from rtstest.sim.orders import Gather, Move
from rtstest.sim.players import HAZARD_OWNER
from rtstest.world import Cell, Terrain, ring_cells

if TYPE_CHECKING:
    from rtstest.sim.buildings import Building
    from rtstest.sim.entities import Entity
    from rtstest.sim.game import Game
    from rtstest.sim.units import Unit

__all__ = ["nearest_hostile", "nearest_base", "random_resource_near", "free_cell_near",
           "free_cells_around", "is_displaceable_by", "displace"]

FREE_CELL_SEARCH_LIMIT = 400
RETALIATE_RANGE_FACTOR = 2.0


def nearest_hostile(game: Game, unit: Unit) -> Entity | None:
    """What an idle combat unit should attack, or None.

    A recent attacker within twice the sight range comes first. Hazard
    creatures see the whole map; others see ``unit.type.sight``.
    """
    sight = unit.type.sight
    if unit.last_attacker is not None:
        attacker = game.entity(unit.last_attacker)
        if (attacker is not None and attacker.alive
                and unit.distance_to(attacker) <= sight * RETALIATE_RANGE_FACTOR):
            return attacker
        unit.last_attacker = None
    radius = math.inf if unit.owner == HAZARD_OWNER else sight
    best, best_d = None, radius
    for e in game.entities():
        if e.alive and game.is_hostile(unit.owner, e.owner):
            d = unit.distance_to(e)
            if d <= best_d:
                best, best_d = e, d
    return best


def nearest_base(game: Game, owner: int, x: float, y: float) -> Building | None:
    """The owner's complete resource-storing building closest to a point."""
    buildings = [b for b in game.buildings_of(owner)
                 if b.complete and b.type.stores_resources]
    if not buildings:
        return None
    return min(buildings, key=lambda b: math.hypot(b.center[0] - x, b.center[1] - y))


def random_resource_near(game: Game, cell: Cell, radius: int) -> Cell | None:
    """A random resource cell other than ``cell`` within ``radius`` cells (square scan).

    Falls back to the nearest resource anywhere when none is that close.
    """
    grid = game.grid
    found = [(x, y)
             for y in range(cell[1] - radius, cell[1] + radius + 1)
             for x in range(cell[0] - radius, cell[0] + radius + 1)
             if (x, y) != cell and grid.in_bounds((x, y))
             and grid.terrain_at((x, y)) == Terrain.RESOURCE]
    if found:
        return game.rng.choice(found)
    return game.nearest_resource(cell, math.inf)


def free_cell_near(game: Game, cells: Iterable[Cell], toward: Cell | None = None) -> Cell | None:
    """A passable cell next to ``cells`` (searching outwards), preferring no unit on it.

    Searches ring by ring; within the nearest ring that has a candidate, the
    cell closest to ``toward`` is chosen when given.
    """
    grid = game.grid
    layer = list(dict.fromkeys(cells))
    unit_cells = {u.cell for u in game.units.values()}
    seen = set(layer)
    fallback = None
    while layer and len(seen) < FREE_CELL_SEARCH_LIMIT:
        nxt = []
        for c in layer:
            for n in grid.adjacent_cells(c):
                if n not in seen:
                    seen.add(n)
                    nxt.append(n)
        passable = [n for n in nxt if grid.is_passable(n)]
        free = [n for n in passable if n not in unit_cells]
        if free:
            return _closest(free, toward)
        if passable and fallback is None:
            fallback = _closest(passable, toward)
        layer = nxt
    return fallback


def _closest(cells: list[Cell], toward: Cell | None) -> Cell:
    """The first of ``cells``, or the one nearest to ``toward`` when given."""
    if toward is None:
        return cells[0]
    return min(cells, key=lambda c: math.hypot(c[0] - toward[0], c[1] - toward[1]))


def free_cells_around(game: Game, cell: Cell, count: int) -> list[Cell]:
    """Up to ``count`` passable cells nearest to ``cell``, for spreading a group."""
    grid = game.grid
    result = [cell] if grid.is_passable(cell) else []
    queue = deque([cell])
    seen = {cell}
    while queue and len(result) < count and len(seen) < FREE_CELL_SEARCH_LIMIT:
        for n in grid.adjacent_cells(queue.popleft()):
            if n in seen:
                continue
            seen.add(n)
            queue.append(n)
            if grid.is_passable(n):
                result.append(n)
    return result[:count]


def is_displaceable_by(game: Game, uid: int, miner: Unit) -> bool:
    """Whether unit ``uid`` must give up its cell to ``miner``: friendly and not gathering."""
    other = game.units.get(uid)
    return (other is not None and other is not miner and other.owner == miner.owner
            and not isinstance(other.order, Gather))


def displace(game: Game, uid: int) -> None:
    """Make a unit give up its reserved cell and step to a random free cell nearby.

    Idle and moving units get a new move order there; units with other
    orders only lose their reservation and pick a new stand cell themselves.
    """
    unit = game.units.get(uid)
    if unit is None:
        return
    unit.release_reservation()
    if unit.order is not None and not isinstance(unit.order, Move):
        return
    cells = [c for ring in (1, 2) for c in ring_cells([unit.cell], ring)
             if game.grid.can_stand(c, uid)]
    if cells:
        unit.set_order(Move(game.rng.choice(cells)))
