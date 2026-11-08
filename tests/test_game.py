"""Headless simulation tests: gathering, training, hazard waves, combat,
reservations and pushback."""

import math

from rtstest.ai import ScriptedAI
from rtstest.sim import (BARRACKS, BASE, CREEP, HAZARD_OWNER, SOLDIER, STARTING_RESOURCES, TICK,
                         WORKER, Build, Game, Gather, Move)
from rtstest.world import Cell, Grid, MapInfo, Terrain, chebyshev, ring_cells


def _small_game() -> Game:
    """One human player on an open 20x20 map, base around (5, 5), resource at (10, 5)."""
    grid = Grid(20, 20)
    grid.set_terrain((10, 5), Terrain.RESOURCE, amount=500)
    game = Game(map_info=MapInfo(grid, [(5, 5)]))
    game.hazard.next_wave_time = 1e9
    return game


def _run(game: Game, seconds: float) -> None:
    for _ in range(round(seconds / TICK)):
        game.step()


def test_worker_gathers_and_deposits():
    game = _small_game()
    worker = game.units_of(0)[0]
    game.order_gather([worker.id], (10, 5))
    _run(game, 30)
    assert game.players[0].resources > STARTING_RESOURCES


def test_train_pays_on_start_and_spawns():
    game = _small_game()
    base = game.buildings_of(0)[0]
    before = len(game.units_of(0))
    assert game.train(base.id, WORKER)
    assert game.players[0].resources == STARTING_RESOURCES
    game.step()
    assert game.players[0].resources == STARTING_RESOURCES - WORKER.cost
    _run(game, WORKER.train_time + 1)
    assert len(game.units_of(0)) == before + 1


def test_only_front_of_queue_is_paid():
    game = _small_game()
    base = game.buildings_of(0)[0]
    for _ in range(3):
        assert game.train(base.id, WORKER)
    game.step()
    assert game.players[0].resources == STARTING_RESOURCES - WORKER.cost


def test_queue_limit_is_five():
    game = _small_game()
    base = game.buildings_of(0)[0]
    assert all(game.train(base.id, WORKER) for _ in range(5))
    assert not game.train(base.id, WORKER)


def test_queue_waits_for_resources():
    game = _small_game()
    base = game.buildings_of(0)[0]
    game.players[0].resources = 0
    before = len(game.units_of(0))
    assert game.train(base.id, WORKER)
    _run(game, WORKER.train_time + 2)
    assert len(game.units_of(0)) == before
    game.players[0].resources = WORKER.cost
    _run(game, WORKER.train_time + 1)
    assert len(game.units_of(0)) == before + 1
    assert game.players[0].resources == 0


def test_cancel_refunds_paid_front_only():
    game = _small_game()
    base = game.buildings_of(0)[0]
    game.train(base.id, WORKER)
    game.train(base.id, WORKER)
    game.step()
    game.cancel_training(base.id, 1)
    assert game.players[0].resources == STARTING_RESOURCES - WORKER.cost
    game.cancel_training(base.id, 0)
    assert game.players[0].resources == STARTING_RESOURCES
    assert base.queue == []


def test_rally_point_sends_new_workers_to_gather():
    game = _small_game()
    base = game.buildings_of(0)[0]
    game.set_rally(base.id, (10, 5))
    game.train(base.id, WORKER)
    _run(game, WORKER.train_time + 1)
    newest = max(game.units_of(0), key=lambda u: u.id)
    assert isinstance(newest.order, Gather)


def test_attack_move_fights_on_the_way():
    game = _small_game()
    soldier = game.spawn_unit(SOLDIER, 0, (2, 15))
    creep = game.spawn_unit(CREEP, HAZARD_OWNER, (10, 15))
    creep.set_order(Move((10, 15)))
    game.order_attack_move([soldier.id], (18, 15))
    _run(game, 30)
    assert creep.id not in game.units
    assert soldier.cell == (18, 15)
    assert soldier.order is None


def test_hazard_wave_spawns_creeps():
    game = _small_game()
    game.hazard.next_wave_time = 0
    game.step()
    assert game.hazard.wave == 1
    assert len(game.units_of(HAZARD_OWNER)) == 3


def test_soldiers_kill_creep():
    game = _small_game()
    for y in (5, 6, 7):
        game.spawn_unit(SOLDIER, 0, (12, y))
    creep = game.spawn_unit(CREEP, HAZARD_OWNER, (16, 6))
    _run(game, 20)
    assert creep.id not in game.units


def test_players_do_not_fight_unprovoked():
    grid = Grid(30, 12)
    game = Game(map_info=MapInfo(grid, [(4, 5), (25, 5)]), human_player=None)
    game.hazard.next_wave_time = 1e9
    a = game.spawn_unit(SOLDIER, 0, (14, 5))
    b = game.spawn_unit(SOLDIER, 1, (15, 5))
    _run(game, 5)
    assert a.hp == a.max_hp and b.hp == b.max_hp


def test_full_game_runs():
    game = Game(seed=1)
    _run(game, 120)
    assert game.hazard.wave >= 2


def _open_game(width: int = 30, height: int = 30) -> Game:
    """One player, base around (3, 3), on an open map with no hazard."""
    game = Game(map_info=MapInfo(Grid(width, height), [(3, 3)]))
    game.hazard.next_wave_time = 1e9
    return game


def test_two_workers_mine_from_different_cells():
    game = _small_game()
    w1, w2 = game.units_of(0)[:2]
    game.order_gather([w1.id, w2.id], (10, 5))
    _run(game, 4)
    assert w1.reserved and w2.reserved and w1.reserved != w2.reserved
    assert w1.cell == w1.reserved and w2.cell == w2.reserved
    assert game.grid.reserved_by(w1.reserved) == w1.id


def test_worker_switches_resource_when_spots_taken():
    game = _open_game()
    game.grid.set_terrain((15, 15), Terrain.RESOURCE)
    game.grid.set_terrain((17, 15), Terrain.RESOURCE)
    for c in ring_cells([(15, 15)], 1):
        game.grid.reserve(c, 999)
    worker = game.units_of(0)[0]
    game.order_gather([worker.id], (15, 15))
    _run(game, 1)
    assert worker.order.resource == (17, 15)
    assert worker.reserved is not None and chebyshev(worker.reserved, (17, 15)) == 1


def test_reservation_released_on_new_order_and_death():
    game = _small_game()
    worker = game.units_of(0)[0]
    game.order_gather([worker.id], (10, 5))
    _run(game, 1)
    spot = worker.reserved
    assert spot is not None
    worker.set_order(None)
    assert game.grid.reserved_by(spot) is None
    game.order_move([worker.id], (15, 15))
    _run(game, 0.5)
    spot = worker.reserved
    worker.hp = 0
    game.step()
    assert game.grid.reserved_by(spot) is None


def test_attackers_surround_target_on_distinct_cells():
    game = _open_game()
    target = game.spawn_unit(CREEP, HAZARD_OWNER, (20, 20), scale=100)
    target.damage = 0
    soldiers = [game.spawn_unit(SOLDIER, 0, (10, 18 + i)) for i in range(4)]
    game.order_attack([s.id for s in soldiers], target.id)
    _run(game, 6)
    cells = [s.cell for s in soldiers]
    assert len(set(cells)) == 4
    assert all(s.distance_to(target) <= SOLDIER.attack_range for s in soldiers)


def test_pushback_separates_idle_units():
    game = _open_game()
    a = game.spawn_unit(SOLDIER, 0, (15, 15))
    b = game.spawn_unit(SOLDIER, 0, (15, 15))
    _run(game, 2)
    assert math.hypot(a.x - b.x, a.y - b.y) >= 0.6


def test_moving_unit_passes_through_stopped_group():
    game = _open_game()
    group = [game.spawn_unit(SOLDIER, 0, (14 + dx, 14 + dy))
             for dx in range(3) for dy in range(3)]
    for s in group:
        game.order_move([s.id], s.cell)
    _run(game, 1)
    runner = game.spawn_unit(WORKER, 0, (10, 15))
    game.order_move([runner.id], (20, 15))
    _run(game, 10)
    assert runner.cell == (20, 15) and runner.order is None
    assert all(s.cell == s.reserved for s in group)


def _walled_resource(game: Game) -> Cell:
    """Resource at (15, 15) whose only free neighbour is (14, 15); returns that cell."""
    game.grid.set_terrain((15, 15), Terrain.RESOURCE, amount=500)
    for c in ring_cells([(15, 15)], 1):
        if c != (14, 15):
            game.grid.set_terrain(c, Terrain.ROCK)
    return (14, 15)


def test_miner_displaces_parked_friendly_unit():
    game = _open_game()
    spot = _walled_resource(game)
    soldier = game.spawn_unit(SOLDIER, 0, (10, 15))
    game.order_move([soldier.id], spot)
    _run(game, 4)
    assert soldier.reserved == spot and soldier.cell == spot
    worker = game.units_of(0)[0]
    game.order_gather([worker.id], (15, 15))
    _run(game, 10)
    assert worker.reserved == spot
    assert soldier.reserved != spot and soldier.cell != spot
    assert game.players[0].resources > STARTING_RESOURCES or worker.carrying > 0


def test_miner_does_not_displace_other_players_units():
    grid = Grid(30, 30)
    game = Game(map_info=MapInfo(grid, [(3, 3), (26, 26)]), human_player=None)
    game.hazard.next_wave_time = 1e9
    spot = _walled_resource(game)
    other = game.spawn_unit(SOLDIER, 1, (10, 15))
    game.order_move([other.id], spot)
    _run(game, 4)
    worker = game.units_of(0)[0]
    game.order_gather([worker.id], (15, 15))
    _run(game, 5)
    assert other.reserved == spot
    assert worker.reserved != spot


def test_base_trains_only_workers():
    game = _small_game()
    base = game.buildings_of(0)[0]
    assert not game.train(base.id, SOLDIER)


def test_can_place_rules():
    game = _open_game()
    assert game.can_place(BARRACKS, (15, 15), 0)
    assert not game.can_place(BARRACKS, (2, 2), 0)
    game.grid.set_terrain((16, 16), Terrain.ROCK)
    assert not game.can_place(BARRACKS, (15, 15), 0)
    miner = game.spawn_unit(WORKER, 0, (20, 20))
    miner.set_order(Gather((25, 25)))
    game.grid.reserve((21, 21), miner.id)
    miner.reserved = (21, 21)
    assert not game.can_place(BARRACKS, (20, 20), 0)


def _build_barracks(game: Game, cell=(15, 15)):
    worker = game.units_of(0)[0]
    game.players[0].resources = 1000
    assert game.order_build([worker.id], BARRACKS, cell)
    return worker


def test_construction_pays_on_start_and_completes():
    game = _open_game()
    worker = _build_barracks(game)
    assert game.players[0].resources == 1000
    _run(game, 8)
    site = [b for b in game.buildings_of(0) if b.type is BARRACKS]
    assert len(site) == 1 and not site[0].complete
    assert game.players[0].resources == 1000 - BARRACKS.cost
    assert isinstance(worker.order, Build)
    assert not game.train(site[0].id, SOLDIER)
    _run(game, BARRACKS.build_time)
    assert site[0].complete and site[0].hp == BARRACKS.max_hp
    assert worker.order is None
    assert game.train(site[0].id, SOLDIER)
    _run(game, SOLDIER.train_time + 1)
    assert any(u.type is SOLDIER for u in game.units_of(0))


def test_construction_stops_without_worker_and_resumes():
    game = _open_game()
    worker = _build_barracks(game)
    _run(game, 10)
    site = [b for b in game.buildings_of(0) if b.type is BARRACKS][0]
    worker.hp = 0
    game.step()
    progress = site.build_progress
    _run(game, 5)
    assert site.build_progress == progress
    other = game.units_of(0)[0]
    assert game.order_resume([other.id], site.id)
    _run(game, BARRACKS.build_time + 10)
    assert site.complete


def test_one_builder_per_building():
    game = _open_game()
    builder = _build_barracks(game)
    _run(game, 8)
    site = [b for b in game.buildings_of(0) if b.type is BARRACKS][0]
    helper = next(u for u in game.units_of(0) if u is not builder)
    game.order_resume([helper.id], site.id)
    _run(game, 8)
    assert helper.order is None
    assert site.builder == builder.id


def test_unfinished_building_does_not_store_resources():
    game = _open_game()
    _build_barracks(game)
    _run(game, 8)
    site = [b for b in game.buildings_of(0) if b.type is BARRACKS][0]
    carrier = game.spawn_unit(WORKER, 0, (site.cell[0] + 3, site.cell[1] + 1))
    carrier.carrying = 10
    carrier.set_order(Gather((0, 0), returning=True))
    before = game.players[0].resources
    _run(game, 0.5)
    assert game.players[0].resources == before
    _run(game, 15)
    assert game.players[0].resources == before + 10


def test_ai_builds_barracks_and_soldiers():
    game = Game(seed=1, human_player=None)
    for p in game.players:
        game.add_controller(ScriptedAI(p.id))
    game.hazard.next_wave_time = 1e9
    _run(game, 240)
    for p in game.players:
        types = {b.type for b in game.buildings_of(p.id) if b.complete}
        assert BARRACKS in types
        assert any(u.type is SOLDIER for u in game.units_of(p.id))
