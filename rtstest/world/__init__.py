"""World: the square tile map and movement over it.

Modules:

- ``grid``: ``Grid`` of ``Terrain`` tiles with resource stocks, building
  occupancy and per-cell unit reservations; ``Cell`` is an ``(x, y)`` int
  tuple.
- ``pathfinding``: ``find_path`` and ``find_path_adjacent``, A* over 8
  neighbours without corner cutting; ``find_stand_cell`` picks a free
  stopping cell in rings around a target.
- ``mapgen``: ``generate`` builds a seeded random ``MapInfo`` (grid + player
  start cells).

This package does not import pygame.
"""
