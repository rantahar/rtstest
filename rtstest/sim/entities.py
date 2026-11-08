"""Entity protocol: what every unit and building offers to the rest of the simulation.

Declared structurally (``typing.Protocol``) so that modules can rely on the
shape of an entity without importing ``units`` or ``buildings``.
"""

from __future__ import annotations

import math
from typing import Protocol

from rtstest.world import Cell

__all__ = ["Entity", "point_rect_distance"]


class Entity(Protocol):
    """Anything on the map with an owner and hit points that can be attacked.

    Attributes: ``id`` (unique among units and buildings), ``owner`` (player
    id or ``HAZARD_OWNER``), ``hp``, ``max_hp``.
    """

    id: int
    owner: int
    hp: float
    max_hp: int

    @property
    def alive(self) -> bool:
        """Whether hp is above zero."""

    def cells(self) -> list[Cell]:
        """Footprint cells."""

    def bounds(self) -> tuple[float, float, float, float]:
        """Footprint rectangle ``(x0, y0, x1, y1)`` in cell units."""

    def take_damage(self, amount: float, attacker: Entity | None = None) -> None:
        """Lose hp; ``attacker`` lets units retaliate."""


def point_rect_distance(px: float, py: float,
                        bounds: tuple[float, float, float, float]) -> float:
    """Distance from a point to an axis-aligned rectangle such as ``Entity.bounds()`` (0 inside)."""
    x0, y0, x1, y1 = bounds
    return math.hypot(max(x0 - px, 0.0, px - x1), max(y0 - py, 0.0, py - y1))
