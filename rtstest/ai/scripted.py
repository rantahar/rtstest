"""Scripted computer players: gather, train, build a barracks, and defend their base.

Workers are trained up to ``WORKER_TARGET``; then one barracks is built in a
ring a few cells from the base (resumed by another worker if its builder
dies), and it trains soldiers continuously.

Each ``ScriptedAI`` thinks once per ``THINK_INTERVAL`` and acts only through
the ``Game`` command methods, as a human player would. Register one per
computer player with ``Game.add_controller``. It never attacks other
players; diplomacy is not implemented yet.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from rtstest.sim import BARRACKS, BASE, HAZARD_OWNER, SOLDIER, WORKER, Attack, Build
from rtstest.world import Cell, ring_cells

if TYPE_CHECKING:
    from rtstest.sim import Building, Game, Unit

__all__ = ["ScriptedAI"]

THINK_INTERVAL = 1.0
WORKER_TARGET = 6
GUARD_RADIUS = 10.0
RESOURCE_SEARCH_RADIUS = 25
BARRACKS_RINGS = range(5, 10)


class ScriptedAI:
    """Rule-based controller for one player."""

    def __init__(self, player_id: int) -> None:
        self.player_id = player_id
        self._timer = 0.0

    def update(self, game: Game, dt: float) -> None:
        """Think when the think timer runs out."""
        self._timer -= dt
        if self._timer > 0:
            return
        self._timer = THINK_INTERVAL
        if game.players[self.player_id].alive:
            self._think(game)

    def _think(self, game: Game) -> None:
        units = game.units_of(self.player_id)
        workers = [u for u in units if u.type is WORKER]
        soldiers = [u for u in units if u.type is SOLDIER]
        for w in workers:
            if w.order is None:
                r = game.nearest_resource(w.cell, RESOURCE_SEARCH_RADIUS)
                if r is not None:
                    game.order_gather([w.id], r)
        buildings = game.buildings_of(self.player_id)
        bases = [b for b in buildings if b.type is BASE]
        barracks = [b for b in buildings if b.type is BARRACKS]
        if not bases:
            return
        base = bases[0]
        if not base.queue and len(workers) < WORKER_TARGET:
            game.train(base.id, WORKER)
        if len(workers) >= WORKER_TARGET:
            self._ensure_barracks(game, base, barracks, workers)
        for b in barracks:
            if b.complete and not b.queue:
                game.train(b.id, SOLDIER)
        cx, cy = base.center
        threats = [c for c in game.units_of(HAZARD_OWNER)
                   if math.hypot(c.x - cx, c.y - cy) <= GUARD_RADIUS]
        for s in soldiers:
            if threats and not isinstance(s.order, Attack):
                target = min(threats, key=s.distance_to)
                game.order_attack([s.id], target.id)
            elif s.order is None and math.hypot(s.x - cx, s.y - cy) > GUARD_RADIUS:
                game.order_move([s.id], base.cell)

    def _ensure_barracks(self, game: Game, base: Building, barracks: list[Building],
                         workers: list[Unit]) -> None:
        """Start one barracks, or resume it if its construction stopped."""
        if any(isinstance(w.order, Build) for w in workers):
            return
        ids = [w.id for w in workers if not w.carrying] or [w.id for w in workers]
        unfinished = [b for b in barracks if not b.complete]
        if unfinished:
            game.order_resume(ids, unfinished[0].id)
            return
        if barracks or game.players[self.player_id].resources < BARRACKS.cost:
            return
        site = self._find_site(game, base)
        if site is not None:
            game.order_build(ids, BARRACKS, site)

    def _find_site(self, game: Game, base: Building) -> Cell | None:
        """First placeable barracks top-left cell in rings around the base."""
        for ring in BARRACKS_RINGS:
            for cell in ring_cells(base.cells(), ring):
                if game.can_place(BARRACKS, cell, self.player_id):
                    return cell
        return None
