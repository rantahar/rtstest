"""Simulation: the game rules, advanced in fixed ticks. No pygame.

Public API (import from ``rtstest.sim``):

- ``Game``: the whole state. ``step()`` advances it by ``TICK`` seconds,
  first stepping each ``Controller`` registered with ``add_controller``;
  lookups and commands (``order_move``, ``order_gather``, ``order_attack``,
  ``order_attack_move``, ``order_build``, ``order_resume``, ``train``,
  ``cancel_training``, ``set_rally``) are shared by UI and computer players.
  See its docstring for the read-only state attributes.
- ``Entity``: protocol of anything attackable; ``Unit`` and ``Building``
  implement it (documented read-only attributes only).
- ``UnitType`` with ``WORKER``, ``SOLDIER``, ``CREEP``; ``BuildingType``
  with ``BASE`` (trains workers, stores resources), ``BARRACKS`` (trains
  soldiers), ``BUILDABLE`` (what workers can build); ``MAX_QUEUE``.
- Orders, to inspect ``Unit.order``: ``Move``, ``Gather``, ``Attack``,
  ``AttackMove``, ``Build``.
- ``Player``, ``HAZARD_OWNER`` (owner of hazard creatures),
  ``STARTING_RESOURCES``.

Modules: ``game`` (state, lookups, commands, step), ``entities`` (protocol),
``unit_types``, ``orders``, ``units`` (Unit, movement, reservations) with its
behaviour mixins ``combat``, ``gathering`` and ``construction`` (which also
places building sites), ``services`` (searches and displacement used during
updates), ``buildings``, ``players``, ``hazard`` (waves), ``steering``
(pushback). Computer players live outside, in ``rtstest.ai``.
"""

from rtstest.sim.buildings import BARRACKS, BASE, BUILDABLE, MAX_QUEUE, Building, BuildingType
from rtstest.sim.entities import Entity
from rtstest.sim.game import TICK, Controller, Game
from rtstest.sim.players import HAZARD_OWNER, STARTING_RESOURCES, Player
from rtstest.sim.orders import Attack, AttackMove, Build, Gather, Move
from rtstest.sim.unit_types import CREEP, SOLDIER, WORKER, UnitType
from rtstest.sim.units import Unit

__all__ = ["Game", "TICK", "Controller", "Entity", "Unit", "Building", "UnitType", "BuildingType",
           "WORKER", "SOLDIER", "CREEP", "BASE", "BARRACKS", "BUILDABLE", "MAX_QUEUE",
           "Move", "Gather", "Attack", "AttackMove", "Build",
           "Player", "HAZARD_OWNER", "STARTING_RESOURCES"]
