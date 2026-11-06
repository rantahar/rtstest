"""Scripted computer players: gather, train, and defend their base.

Each ``ScriptedAI`` thinks once per ``THINK_INTERVAL`` and acts only through
the ``Game`` command methods, as a human player would. It never attacks other
players; diplomacy is not implemented yet.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from rtstest.sim.players import HAZARD_OWNER
from rtstest.sim.units import SOLDIER, WORKER, Attack

if TYPE_CHECKING:
    from rtstest.sim.game import Game

THINK_INTERVAL = 1.0
WORKER_TARGET = 6
GUARD_RADIUS = 10.0
RESOURCE_SEARCH_RADIUS = 25


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
        bases = game.buildings_of(self.player_id)
        if not bases:
            return
        base = bases[0]
        if not base.queue:
            game.train(base.id, WORKER if len(workers) < WORKER_TARGET else SOLDIER)
        cx, cy = base.center
        threats = [c for c in game.units_of(HAZARD_OWNER)
                   if math.hypot(c.x - cx, c.y - cy) <= GUARD_RADIUS]
        for s in soldiers:
            if threats and not isinstance(s.order, Attack):
                target = min(threats, key=s.distance_to)
                game.order_attack([s.id], target.id)
            elif s.order is None and math.hypot(s.x - cx, s.y - cy) > GUARD_RADIUS:
                game.order_move([s.id], base.cell)
