"""Simulation: the game rules, advanced in fixed ticks. No pygame.

Modules:

- ``game``: ``Game`` holds the whole state, advances it with ``step()``,
  answers world queries and exposes the command interface (``order_move``,
  ``order_gather``, ``order_attack``, ``set_rally``, ``train``) used by UI
  and AI alike.
- ``units``: ``UnitType`` stats (``WORKER``, ``SOLDIER``, ``CREEP``),
  orders (``Move``, ``Gather``, ``Attack``) and ``Unit`` behaviour.
- ``buildings``: ``BuildingType`` (``BASE``) and ``Building`` with a
  training queue and rally point.
- ``players``: ``Player`` (resources, colour) and ``HAZARD_OWNER``.
- ``hazard``: ``Hazard``, the growing waves of hostile creatures.
- ``ai``: ``ScriptedAI``, rule-based computer players.
"""
