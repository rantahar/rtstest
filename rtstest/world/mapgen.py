"""Random map generation: terrain blobs, resource patches and player starts.

``generate`` is deterministic for a given seed. Each start cell is the centre
of a cleared grass area that fits a 3x3 base with room around it, and has a
resource patch nearby.
"""

import math
import random
from dataclasses import dataclass

from rtstest.world.grid import Cell, Grid, Terrain, chebyshev

__all__ = ["MapInfo", "generate"]

START_CLEAR_RADIUS = 5
START_RING_FRACTION = 0.33
HOME_PATCH_DISTANCE = 7
HOME_PATCH_CELLS = 12
BLOB_DENSITY = ((Terrain.ROCK, 1 / 300), (Terrain.WATER, 1 / 600),
                (Terrain.RESOURCE, 1 / 350))
BLOB_SIZE = (4, 14)
_STEPS = ((1, 0), (-1, 0), (0, 1), (0, -1))


@dataclass
class MapInfo:
    """A generated map: the grid and one start cell per player."""

    grid: Grid
    starts: list[Cell]


def generate(width: int = 64, height: int = 64, n_players: int = 3,
             seed: int = 0) -> MapInfo:
    """Build a random map with ``n_players`` start cells spaced on a ring."""
    rng = random.Random(seed)
    grid = Grid(width, height)
    for terrain, density in BLOB_DENSITY:
        for _ in range(max(1, round(width * height * density))):
            _blob(grid, rng, terrain, rng.randint(*BLOB_SIZE))
    starts = _start_cells(width, height, n_players, rng)
    for start in starts:
        _clear(grid, start, START_CLEAR_RADIUS)
    for start in starts:
        _home_patch(grid, rng, start, starts)
    return MapInfo(grid, starts)


def _blob(grid: Grid, rng: random.Random, terrain: Terrain, size: int) -> None:
    """Paint a random-walk blob of ``size`` steps."""
    x, y = rng.randrange(grid.width), rng.randrange(grid.height)
    for _ in range(size):
        grid.set_terrain((x, y), terrain)
        dx, dy = rng.choice(_STEPS)
        x = min(max(x + dx, 0), grid.width - 1)
        y = min(max(y + dy, 0), grid.height - 1)


def _start_cells(width: int, height: int, n: int, rng: random.Random) -> list[Cell]:
    """Start cells evenly spaced on a ring around the map centre."""
    cx, cy = width / 2, height / 2
    radius = min(width, height) * START_RING_FRACTION
    a0 = rng.uniform(0, 2 * math.pi)
    return [(int(cx + radius * math.cos(a0 + 2 * math.pi * i / n)),
             int(cy + radius * math.sin(a0 + 2 * math.pi * i / n)))
            for i in range(n)]


def _clear(grid: Grid, center: Cell, radius: int) -> None:
    """Turn a disc of cells into grass."""
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            cell = (center[0] + dx, center[1] + dy)
            if dx * dx + dy * dy <= radius * radius and grid.in_bounds(cell):
                grid.set_terrain(cell, Terrain.GRASS)


def _home_patch(grid: Grid, rng: random.Random, start: Cell, starts: list[Cell]) -> None:
    """Place a small resource patch a few cells from a start, away from bases."""
    angle = rng.uniform(0, 2 * math.pi)
    px = min(max(start[0] + round(HOME_PATCH_DISTANCE * math.cos(angle)), 1), grid.width - 2)
    py = min(max(start[1] + round(HOME_PATCH_DISTANCE * math.sin(angle)), 1), grid.height - 2)
    for _ in range(HOME_PATCH_CELLS):
        cell = (px + rng.randint(-1, 1), py + rng.randint(-1, 1))
        if grid.in_bounds(cell) and all(chebyshev(cell, s) > 2 for s in starts):
            grid.set_terrain(cell, Terrain.RESOURCE)
