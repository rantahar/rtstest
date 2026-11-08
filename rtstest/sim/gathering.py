"""Gathering behaviour of workers: claim a mining spot, mine, carry loads home.

``GatheringBehaviour`` is a mixin of ``Unit``. A worker checks at most one
resource cell per tick for a free mining spot next to it, taking over a spot
held by a friendly non-gathering unit if needed (that unit is displaced),
and otherwise switches to a random nearby resource for the next tick. It
mines only while standing on its reserved spot and releases the spot when
it leaves to deposit at the nearest complete base. Mining out a cell
opens a hazard pit (``Hazard.resource_depleted``).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from rtstest.sim.services import displace, is_displaceable_by, nearest_base, random_resource_near
from rtstest.world import Cell, Terrain, find_path, find_stand_cell

if TYPE_CHECKING:
    from rtstest.sim.game import Game

__all__ = ["GatheringBehaviour"]

GATHER_TIME = 0.5
GATHER_SEARCH_RADIUS = 10
DEPOSIT_RANGE = 1.0
GATHER_SWITCH_RADIUS = 3


def _touches(a: Cell, b: Cell) -> bool:
    """Whether two different cells are 8-neighbours."""
    return a != b and max(abs(a[0] - b[0]), abs(a[1] - b[1])) == 1


class GatheringBehaviour:
    """``Unit`` mixin: the ``Gather`` order."""

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
            self.release_reservation()
            self._return_load(game, dt)
            return
        stand = self.reserved
        if stand is None or not _touches(stand, order.resource):
            self._find_mining_spot(game)
            return
        if self.cell == stand and not self.path:
            self._work_timer += dt
            if self._work_timer >= GATHER_TIME:
                self._work_timer = 0.0
                self.carrying += grid.take_resource(order.resource, 1)
                if grid.terrain_at(order.resource) != Terrain.RESOURCE:
                    game.hazard.resource_depleted(game, order.resource, self.owner)
                if self.carrying >= self.type.gather_capacity:
                    order.returning = True
            return
        if not self.path:
            path = find_path(grid, self.cell, stand)
            if path is None:
                self.release_reservation()
                self._switch_resource(game)
                return
            self.path = path
        self._step(game, dt)

    def _find_mining_spot(self, game: Game) -> None:
        """Check the current resource cell once for a free spot; else switch resource.

        When every spot is taken, a spot held by a friendly unit that is not
        gathering is taken over and that unit is moved aside (``displace``).
        """
        order = self.order
        stand = find_stand_cell(self._grid, self.cell, [order.resource], self.id,
                                can_displace=lambda uid: is_displaceable_by(game, uid, self))
        holder = self._grid.reserved_by(stand) if stand is not None else None
        if holder is not None and holder != self.id:
            displace(game, holder)
        if stand is not None and self._reserve(stand):
            self.path = []
            self._work_timer = 0.0
        else:
            self._switch_resource(game)

    def _switch_resource(self, game: Game) -> None:
        """Retarget to a random resource cell nearby, to be checked next tick."""
        alt = random_resource_near(game, self.order.resource, GATHER_SWITCH_RADIUS)
        if alt is not None:
            self.order.resource = alt
            self.path = []

    def _return_load(self, game: Game, dt: float) -> None:
        """Walk to the nearest own base and deposit what we carry."""
        base = nearest_base(game, self.owner, self.x, self.y)
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
