"""Combat behaviour of units: idle scanning, attack and attack-move.

``CombatBehaviour`` is a mixin of ``Unit``: its methods run as unit methods
and use the unit's movement and reservation helpers. Attackers reserve a
free cell in ring 1 around the target (in range); when ring 1 is full they
wait in outer rings, re-checking at most every ``REPATH_INTERVAL``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from rtstest.sim.orders import Attack
from rtstest.sim.services import nearest_hostile
from rtstest.sim.unit_types import REPATH_INTERVAL
from rtstest.world import find_path, find_path_adjacent, find_stand_cell

if TYPE_CHECKING:
    from rtstest.sim.entities import Entity
    from rtstest.sim.game import Game

__all__ = ["CombatBehaviour"]

SCAN_INTERVAL = 0.5
ATTACK_MAX_RING = 3


class CombatBehaviour:
    """``Unit`` mixin: what idle, attacking and attack-moving units do each tick."""

    def _idle(self, game: Game, dt: float) -> None:
        """Combat units periodically look for something hostile to attack."""
        self._scan_timer -= dt
        if self._scan_timer > 0 or self.type.gather_capacity:
            return
        self._scan_timer = SCAN_INTERVAL
        enemy = nearest_hostile(game, self)
        if enemy is not None:
            self.set_order(Attack(enemy.id))

    def _attack(self, game: Game, dt: float) -> None:
        target = game.entity(self.order.target_id)
        if target is None or not target.alive:
            self.set_order(None)
            return
        self._engage(game, target, dt)

    def _attack_move(self, game: Game, dt: float) -> None:
        order = self.order
        target = game.entity(order.engaged) if order.engaged is not None else None
        if target is None or not target.alive:
            if order.engaged is not None:
                order.engaged = None
                order.claimed = False
                self.path = []
                self._path_key = None
            self._scan_timer -= dt
            if self._scan_timer <= 0:
                self._scan_timer = SCAN_INTERVAL
                target = nearest_hostile(game, self)
                if target is not None:
                    order.engaged = target.id
                    self.path = []
                    self._path_key = None
        if target is not None:
            self._engage(game, target, dt)
            return
        if not order.claimed:
            self._claim_destination(order)
        self._walk_to(game, order.target, dt)

    def _engage(self, game: Game, target: Entity, dt: float) -> None:
        """Hit the target when in range, otherwise go to a reserved cell near it.

        The stand cell is the nearest free cell in the rings around the target
        (ring 1 is in range; outer rings are waiting places). It is
        re-chosen at most every ``REPATH_INTERVAL``, when the target has
        moved or the unit is waiting with no path.
        """
        if self.distance_to(target) <= self.type.attack_range:
            self.path = []
            self._path_key = None
            if self.reserved != self.cell:
                self._reserve(self.cell)
            if self._cooldown <= 0:
                target.take_damage(self.damage, self)
                self._cooldown = self.type.attack_cooldown
            return
        cells = target.cells()
        key = tuple(cells)
        if self._repath_timer <= 0 and (key != self._path_key or not self.path):
            self._repath_timer = REPATH_INTERVAL
            self._path_key = key
            stand = find_stand_cell(self._grid, self.cell, cells, self.id, 1, ATTACK_MAX_RING)
            if stand is not None and self._reserve(stand):
                self.path = find_path(self._grid, self.cell, stand) or []
            else:
                self.release_reservation()
                self.path = find_path_adjacent(self._grid, self.cell, cells) or []
        self._step(game, dt)
