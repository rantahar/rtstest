"""World: the square tile map and movement over it.

Modules:

- ``grid``: ``Grid`` of ``Terrain`` tiles with resource stocks and building
  occupancy; ``Cell`` is an ``(x, y)`` int tuple.
- ``pathfinding``: ``find_path`` and ``find_path_adjacent``, A* over 8
  neighbours without corner cutting.
- ``mapgen``: ``generate`` builds a seeded random ``MapInfo`` (grid + player
  start cells).

This package does not import pygame.
"""
