"""Game state: map, players, units, buildings and the fixed-step update.

``Game.step`` advances everything by ``TICK`` seconds. The lookups and the
``order_*`` (including ``order_build`` and ``order_resume``), ``set_rally``,
``train`` and ``cancel_training`` commands are the interface shared by the UI
and computer players. Services that units and buildings need while updating
live in ``services`` and ``construction``. Hostility between owners is
decided in one place, ``is_hostile``.
"""

from __future__ import annotations

import math
import random
from collections.abc import Iterable, Iterator
from typing import Protocol

from rtstest.sim.buildings import BASE, Building, BuildingType
from rtstest.sim.construction import can_place
from rtstest.sim.entities import Entity
from rtstest.sim.hazard import Hazard
from rtstest.sim.orders import Attack, AttackMove, Build, Gather, Move
from rtstest.sim.players import HAZARD_OWNER, make_players
from rtstest.sim.services import free_cell_near, free_cells_around
from rtstest.sim.steering import apply_pushback
from rtstest.sim.unit_types import WORKER, UnitType
from rtstest.sim.units import Unit
from rtstest.world import Cell, MapInfo, Terrain, generate

__all__ = ["Game", "TICK", "Controller"]

TICK = 1 / 20
STARTING_WORKERS = 3


class Controller(Protocol):
    """A computer player (or any other driver) stepped with the game."""

    def update(self, game: Game, dt: float) -> None:
        """Look at the game and issue commands; called at the start of each tick."""


class Game:
    """The complete simulation state.

    Public attributes (read-only outside ``sim``): ``grid``, ``players``
    (list indexed by player id), ``units`` and ``buildings`` (dicts by id),
    ``time`` (seconds), ``hazard`` (its ``next_wave_time`` may be set, e.g.
    by tests). Properties: ``wave``, ``next_wave_in``.

    For UI and computer players: ``step``, ``add_controller``, the lookups (``entity``,
    ``entity_at``, ``entities``, ``units_of``, ``buildings_of``,
    ``units_in_rect``, ``nearest_resource``, ``can_place``) and the commands
    (``order_*``, ``train``, ``cancel_training``, ``set_rally``).

    Package-internal: ``spawn_unit``, ``place_building``, ``is_hostile``,
    ``entities``, ``rng`` (seeded random source for the simulation).
    """

    def __init__(self, width: int = 64, height: int = 64, n_players: int = 3,
                 seed: int = 0, human_player: int | None = 0,
                 map_info: MapInfo | None = None) -> None:
        """Start a game: one base and a few workers per player.

        With ``map_info`` given, its start cells decide the player count and
        ``width``, ``height`` and ``n_players`` are ignored.
        """
        if map_info is None:
            map_info = generate(width, height, n_players, seed)
        self.grid = map_info.grid
        self.players = make_players(len(map_info.starts), human_player)
        self.units: dict[int, Unit] = {}
        self.buildings: dict[int, Building] = {}
        self.hazard = Hazard(seed)
        self.rng = random.Random(seed + 2)
        self.time = 0.0
        self._next_id = 1
        self._controllers: list[Controller] = []
        for player, (sx, sy) in zip(self.players, map_info.starts):
            base = self.place_building(BASE, player.id, (sx - 1, sy - 1))
            if base is None:
                raise ValueError(f"no room for a base at start {(sx, sy)}")
            for _ in range(STARTING_WORKERS):
                cell = free_cell_near(self, base.cells())
                if cell is not None:
                    self.spawn_unit(WORKER, player.id, cell)

    @property
    def wave(self) -> int:
        """Number of hazard waves spawned so far."""
        return self.hazard.wave

    @property
    def next_wave_in(self) -> float:
        """Seconds until the next hazard wave (0 if due)."""
        return max(0.0, self.hazard.next_wave_time - self.time)

    def add_controller(self, controller: Controller) -> None:
        """Step ``controller`` at the start of every tick, e.g. a computer player."""
        self._controllers.append(controller)

    # --- creation and lookup -------------------------------------------

    def spawn_unit(self, utype: UnitType, owner: int, cell: Cell,
                   scale: float = 1.0) -> Unit:
        """Create a unit at a cell; ``scale`` multiplies hp and damage."""
        unit = Unit(self._new_id(), utype, owner, cell, self.grid, scale)
        self.units[unit.id] = unit
        return unit

    def place_building(self, btype: BuildingType, owner: int, cell: Cell,
                       complete: bool = True) -> Building | None:
        """Create a building with top-left at ``cell`` if all its cells are passable."""
        building = Building(0, btype, owner, cell, complete)
        if not all(self.grid.is_passable(c) for c in building.cells()):
            return None
        building.id = self._new_id()
        self.grid.occupy(building.cells())
        self.buildings[building.id] = building
        return building

    def entity(self, eid: int) -> Entity | None:
        """The live unit or building with this id, if any."""
        return self.units.get(eid) or self.buildings.get(eid)

    def entities(self) -> Iterator[Entity]:
        """All units and buildings."""
        yield from self.units.values()
        yield from self.buildings.values()

    def units_of(self, owner: int) -> list[Unit]:
        return [u for u in self.units.values() if u.owner == owner]

    def buildings_of(self, owner: int) -> list[Building]:
        return [b for b in self.buildings.values() if b.owner == owner]

    def entity_at(self, wx: float, wy: float) -> Entity | None:
        """The unit (preferred) or building under a world point."""
        best, best_d = None, 0.5
        for u in self.units.values():
            d = math.hypot(u.x - wx, u.y - wy)
            if d <= best_d:
                best, best_d = u, d
        if best is not None:
            return best
        for b in self.buildings.values():
            x0, y0, x1, y1 = b.bounds()
            if x0 <= wx < x1 and y0 <= wy < y1:
                return b
        return None

    def units_in_rect(self, x0: float, y0: float, x1: float, y1: float,
                      owner: int) -> list[Unit]:
        """Units of ``owner`` whose centre lies in the rectangle (any corner order)."""
        x0, x1 = sorted((x0, x1))
        y0, y1 = sorted((y0, y1))
        return [u for u in self.units.values()
                if u.owner == owner and x0 <= u.x <= x1 and y0 <= u.y <= y1]

    # --- world queries ---------------------------------------------------

    def is_hostile(self, a: int, b: int) -> bool:
        """Whether owner ``a`` automatically attacks owner ``b``.

        Only the hazard and players are mutually hostile; players attack each
        other only on explicit orders.
        """
        return a != b and (a == HAZARD_OWNER or b == HAZARD_OWNER)

    def can_place(self, btype: BuildingType, cell: Cell, owner: int) -> bool:
        """Whether ``owner`` may place ``btype`` with top-left ``cell`` now.

        Every cell must be passable and either unreserved or reserved by one
        of the owner's own idle or moving units (which will be moved aside).
        """
        return can_place(self, btype, cell, owner)

    def nearest_resource(self, cell: Cell, radius: float) -> Cell | None:
        """The closest resource cell within ``radius`` cells, if any."""
        best, best_d = None, radius
        for r in self.grid.resource_cells():
            d = math.hypot(r[0] - cell[0], r[1] - cell[1])
            if d <= best_d:
                best, best_d = r, d
        return best

    # --- commands --------------------------------------------------------

    def order_move(self, unit_ids: Iterable[int], cell: Cell) -> None:
        """Send units to a cell, spread over the free cells around it."""
        units = self._units(unit_ids)
        targets = free_cells_around(self, cell, len(units))
        if not targets:
            return
        for i, u in enumerate(units):
            u.set_order(Move(targets[i % len(targets)]))

    def order_gather(self, unit_ids: Iterable[int], cell: Cell) -> None:
        """Workers harvest the resource cell; other units move next to it."""
        units = self._units(unit_ids)
        if self.grid.terrain_at(cell) != Terrain.RESOURCE:
            self.order_move([u.id for u in units], cell)
            return
        for u in units:
            if u.type.gather_capacity:
                u.set_order(Gather(cell))
        others = [u.id for u in units if not u.type.gather_capacity]
        if others:
            self.order_move(others, cell)

    def order_attack(self, unit_ids: Iterable[int], target_id: int) -> None:
        """Units attack an entity (any owner other than their own)."""
        target = self.entity(target_id)
        if target is None:
            return
        for u in self._units(unit_ids):
            if u.owner != target.owner:
                u.set_order(Attack(target_id))

    def order_attack_move(self, unit_ids: Iterable[int], cell: Cell) -> None:
        """Units walk to a cell, fighting hostiles they meet on the way."""
        units = self._units(unit_ids)
        targets = free_cells_around(self, cell, len(units))
        if not targets:
            return
        for i, u in enumerate(units):
            u.set_order(AttackMove(targets[i % len(targets)]))

    def order_build(self, unit_ids: Iterable[int], btype: BuildingType, cell: Cell) -> bool:
        """Send one worker from the units to build ``btype`` with top-left ``cell``.

        The nearest worker to the site is chosen; False if there is none or
        the site is not placeable now.
        """
        workers = [u for u in self._units(unit_ids) if u.type.gather_capacity]
        if not workers or not self.can_place(btype, cell, workers[0].owner):
            return False
        cx, cy = cell[0] + btype.size[0] / 2, cell[1] + btype.size[1] / 2
        worker = min(workers, key=lambda u: math.hypot(u.x - cx, u.y - cy))
        worker.set_order(Build(btype, cell))
        return True

    def order_resume(self, unit_ids: Iterable[int], building_id: int) -> bool:
        """Send one worker to continue an own unfinished building; False if not possible."""
        b = self.buildings.get(building_id)
        workers = [u for u in self._units(unit_ids) if u.type.gather_capacity]
        if b is None or b.complete or not workers or workers[0].owner != b.owner:
            return False
        worker = min(workers, key=lambda u: math.hypot(u.x - b.center[0], u.y - b.center[1]))
        worker.set_order(Build(b.type, b.cell, b.id))
        return True

    def set_rally(self, building_id: int, cell: Cell | None) -> None:
        """Set (or clear with None) where a building sends the units it trains."""
        b = self.buildings.get(building_id)
        if b is not None and (cell is None or self.grid.in_bounds(cell)):
            b.rally = cell

    def train(self, building_id: int, utype: UnitType) -> bool:
        """Queue a unit (paid when its training starts); False if not allowed or queue full."""
        b = self.buildings.get(building_id)
        if b is None or not b.can_enqueue(utype):
            return False
        b.queue.append(utype)
        return True

    def cancel_training(self, building_id: int, index: int) -> None:
        """Remove a queued unit, refunding it if its training was already paid."""
        b = self.buildings.get(building_id)
        if b is not None:
            self.players[b.owner].resources += b.cancel(index)

    # --- update ----------------------------------------------------------

    def step(self) -> None:
        """Advance the whole game by one ``TICK``."""
        self.time += TICK
        for controller in self._controllers:
            controller.update(self, TICK)
        self.hazard.update(self)
        for b in list(self.buildings.values()):
            b.update(self, TICK)
        for u in list(self.units.values()):
            if u.alive:
                u.update(self, TICK)
        apply_pushback(list(self.units.values()), self.grid, TICK)
        self._remove_dead()

    def _remove_dead(self) -> None:
        for uid in [uid for uid, u in self.units.items() if not u.alive]:
            self.units[uid].release_reservation()
            del self.units[uid]
        for bid in [bid for bid, b in self.buildings.items() if not b.alive]:
            self.grid.release(self.buildings[bid].cells())
            del self.buildings[bid]
        owners = {e.owner for e in self.entities()}
        for p in self.players:
            p.alive = p.id in owners

    def _new_id(self) -> int:
        self._next_id += 1
        return self._next_id - 1

    def _units(self, unit_ids: Iterable[int]) -> list[Unit]:
        return [self.units[i] for i in unit_ids if i in self.units]
