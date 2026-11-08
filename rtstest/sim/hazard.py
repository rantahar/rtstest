"""Environmental hazard: mined-out resource cells open pits that spawn creeps.

Every resource cell that is mined out opens one pit, a hazard-owned
``PIT`` building that is hard to destroy. It appears a few cells from the
depleted cell, preferably on the side towards the base of the player who
mined it, and not right next to a resource patch. Each pit spawns a creep
every ``PIT_SPAWN_INTERVAL`` while fewer than ``PIT_MAX_CREEPS`` of its
creeps are alive. Creeps grow tougher with game time (hp and damage scale),
belong to ``HAZARD_OWNER`` and hunt the nearest player unit or building.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from rtstest.sim.buildings import PIT
from rtstest.sim.players import HAZARD_OWNER
from rtstest.sim.services import free_cell_near, nearest_base
from rtstest.sim.unit_types import CREEP
from rtstest.world import Cell, Terrain, ring_cells

if TYPE_CHECKING:
    from rtstest.sim.game import Game

__all__ = ["Hazard"]

PIT_SPAWN_INTERVAL = 20.0
PIT_MAX_CREEPS = 3
PIT_RINGS = range(2, 6)
STRENGTH_GROWTH_PER_MINUTE = 0.1


@dataclass
class _Pit:
    """Spawn state of one pit."""

    next_spawn: float
    creeps: list[int] = field(default_factory=list)


class Hazard:
    """Opens pits on mined-out resources and spawns their creeps.

    Public (read-only outside ``sim``): ``pit_count``. Package-internal:
    ``resource_depleted``, ``update``.
    """

    def __init__(self, seed: int = 0) -> None:
        self._rng = random.Random(seed + 1)
        self._pits: dict[int, _Pit] = {}

    @property
    def pit_count(self) -> int:
        """Number of open pits."""
        return len(self._pits)

    def resource_depleted(self, game: Game, cell: Cell, owner: int) -> None:
        """Open a pit for a resource cell that ``owner``'s worker just mined out."""
        site = self._pit_site(game, cell, owner)
        pit = game.place_building(PIT, HAZARD_OWNER, site)
        if pit is not None:
            self._pits[pit.id] = _Pit(game.time + PIT_SPAWN_INTERVAL)

    def update(self, game: Game) -> None:
        """Forget destroyed pits; let each pit spawn a creep when due and below its cap."""
        for pid, state in list(self._pits.items()):
            pit = game.buildings.get(pid)
            if pit is None:
                del self._pits[pid]
                continue
            state.creeps = [c for c in state.creeps if c in game.units]
            if game.time < state.next_spawn:
                continue
            if len(state.creeps) >= PIT_MAX_CREEPS:
                state.next_spawn = game.time + PIT_SPAWN_INTERVAL
                continue
            spot = free_cell_near(game, pit.cells())
            if spot is None:
                continue
            scale = 1 + STRENGTH_GROWTH_PER_MINUTE * game.time / 60
            state.creeps.append(game.spawn_unit(CREEP, HAZARD_OWNER, spot, scale).id)
            state.next_spawn = game.time + PIT_SPAWN_INTERVAL

    def _pit_site(self, game: Game, cell: Cell, owner: int) -> Cell:
        """Where the pit for depleted ``cell`` opens.

        A random free cell in rings ``PIT_RINGS`` around it that is not next
        to a resource, preferring cells closer to the miner's nearest base
        than the depleted cell is. Falls back to the depleted cell itself.
        """
        grid = game.grid
        occupied = {u.cell for u in game.units.values()}
        candidates = []
        for ring in PIT_RINGS:
            for c in ring_cells([cell], ring):
                if (grid.in_bounds(c) and grid.is_passable(c) and c not in occupied
                        and grid.reserved_by(c) is None and not self._near_resource(game, c)):
                    candidates.append(c)
        if not candidates:
            return cell
        base = nearest_base(game, owner, cell[0] + 0.5, cell[1] + 0.5)
        if base is not None:
            bx, by = base.center
            limit = math.hypot(cell[0] + 0.5 - bx, cell[1] + 0.5 - by)
            closer = [c for c in candidates
                      if math.hypot(c[0] + 0.5 - bx, c[1] + 0.5 - by) < limit]
            candidates = closer or candidates
        return self._rng.choice(candidates)

    @staticmethod
    def _near_resource(game: Game, cell: Cell) -> bool:
        """Whether ``cell`` touches a resource cell."""
        grid = game.grid
        return any(grid.in_bounds(c) and grid.terrain_at(c) == Terrain.RESOURCE
                   for c in ring_cells([cell], 1))
