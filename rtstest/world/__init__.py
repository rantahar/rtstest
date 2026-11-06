"""World: the square tile map and movement over it. No pygame.

Public API (import from ``rtstest.world``):

- ``Cell``: an ``(x, y)`` int tuple. ``chebyshev(a, b)``: 8-direction grid distance.
- ``Terrain``: tile kinds; only ``GRASS`` is walkable.
- ``Grid``: terrain tiles with resource stocks, building occupancy and
  per-cell unit reservations (a unit's chosen stopping cell).
- ``find_path``, ``find_path_adjacent``: A* over 8 neighbours without corner
  cutting. ``find_stand_cell``: nearest free stopping cell in rings around a
  target; ``ring_cells``: the cells of one such ring.
- ``MapInfo``, ``generate``: seeded random map with player start cells.

Modules: ``grid``, ``pathfinding``, ``mapgen``.
"""

from rtstest.world.grid import Cell, Grid, Terrain, chebyshev
from rtstest.world.mapgen import MapInfo, generate
from rtstest.world.pathfinding import find_path, find_path_adjacent, find_stand_cell, ring_cells

__all__ = ["Cell", "Terrain", "Grid", "chebyshev", "find_path", "find_path_adjacent",
           "find_stand_cell", "ring_cells", "MapInfo", "generate"]
