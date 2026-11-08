"""Computer players: they drive a ``Game`` only through its public API, like the UI.

Public API (import from ``rtstest.ai``):

- ``ScriptedAI(player_id)``: rule-based player (gather, train, build a
  barracks, defend the base); a ``rtstest.sim.Controller``, registered with
  ``Game.add_controller``.

Modules: ``scripted``.
"""

from rtstest.ai.scripted import ScriptedAI

__all__ = ["ScriptedAI"]
