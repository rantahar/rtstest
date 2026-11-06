"""rtstest: a cohabitive real-time strategy prototype.

Players survive an environmental hazard that grows over time. They share the
map's resources, so they may compete, or they may cooperate and defend
together; there is no shared victory condition.

Subpackages:

- ``rtstest.world``: square tile grid, A* pathfinding and map generation.
  No pygame.
- ``rtstest.sim``: game rules (units, buildings, players, hazard, computer
  players) advanced in fixed ticks by ``rtstest.sim.game.Game``. No pygame.
- ``rtstest.ui``: pygame sprites, rendering and input.

Run the game with ``python -m rtstest`` or the ``rtstest`` command.
"""
