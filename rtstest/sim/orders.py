"""Orders: what a unit is currently doing, as small mutable records.

``Unit.update`` dispatches on the order type; the behaviour for each lives
in ``units`` (Move), ``combat`` (Attack, AttackMove, idle), ``gathering``
(Gather) and ``construction`` (Build). ``None`` means idle.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Union

from rtstest.world import Cell

if TYPE_CHECKING:
    from rtstest.sim.buildings import BuildingType

__all__ = ["Move", "Gather", "Attack", "AttackMove", "Build", "Order"]


@dataclass
class Move:
    """Walk to a cell (moved to the nearest free cell when the order is claimed)."""

    target: Cell
    claimed: bool = False


@dataclass
class Gather:
    """Harvest a resource cell and carry full loads to the nearest own base."""

    resource: Cell
    returning: bool = False


@dataclass
class Attack:
    """Chase and hit the entity with this id until it is gone."""

    target_id: int


@dataclass
class AttackMove:
    """Walk to a cell, fighting any hostile met on the way, then carry on."""

    target: Cell
    engaged: int | None = None
    claimed: bool = False


@dataclass
class Build:
    """Construct a building with top-left ``cell``, or resume ``building_id``.

    The site is placed and paid for when the worker arrives next to it.
    """

    btype: BuildingType
    cell: Cell
    building_id: int | None = None


Order = Union[Move, Gather, Attack, AttackMove, Build, None]
