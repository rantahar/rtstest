"""Environmental hazard: waves of hostile creatures that grow over time.

Each wave spawns at a random passable map-edge cell. Waves get bigger, the
creatures get tougher (hp and damage scale), and the gap between waves
shrinks down to a floor. Creatures belong to ``HAZARD_OWNER`` and hunt the
nearest player unit or building.
"""

from __future__ import annotations

import random
from typing import TYPE_CHECKING

from rtstest.sim.players import HAZARD_OWNER
from rtstest.sim.units import CREEP, Unit
from rtstest.world import Cell, Grid

if TYPE_CHECKING:
    from rtstest.sim.game import Game

__all__ = ["Hazard"]

FIRST_WAVE_TIME = 45.0
BASE_INTERVAL = 45.0
MIN_INTERVAL = 15.0
INTERVAL_DECAY = 2.5
BASE_WAVE_SIZE = 2
STRENGTH_GROWTH = 0.15
EDGE_TRIES = 200


class Hazard:
    """Schedules and spawns hazard waves."""

    def __init__(self, seed: int = 0) -> None:
        self._rng = random.Random(seed + 1)
        self.wave = 0
        self.next_wave_time = FIRST_WAVE_TIME

    def update(self, game: Game) -> None:
        """Spawn a wave when its time has come."""
        if game.time >= self.next_wave_time:
            self.spawn_wave(game)

    def spawn_wave(self, game: Game) -> list[Unit]:
        """Spawn the next wave now, schedule the one after, return the creatures."""
        self.wave += 1
        scale = 1 + STRENGTH_GROWTH * (self.wave - 1)
        edge = self._edge_cell(game.grid)
        spawned = []
        if edge is not None:
            for _ in range(BASE_WAVE_SIZE + self.wave):
                cell = game.free_cell_near([edge])
                if cell is None:
                    break
                spawned.append(game.spawn_unit(CREEP, HAZARD_OWNER, cell, scale))
        self.next_wave_time = game.time + max(MIN_INTERVAL,
                                              BASE_INTERVAL - INTERVAL_DECAY * self.wave)
        return spawned

    def _edge_cell(self, grid: Grid) -> Cell | None:
        """A random passable cell on the map border."""
        for _ in range(EDGE_TRIES):
            side = self._rng.randrange(4)
            if side < 2:
                cell = (self._rng.randrange(grid.width), 0 if side == 0 else grid.height - 1)
            else:
                cell = (0 if side == 2 else grid.width - 1, self._rng.randrange(grid.height))
            if grid.is_passable(cell):
                return cell
        return None
