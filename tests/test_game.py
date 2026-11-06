"""Headless simulation tests: gathering, training, hazard waves and combat."""

from rtstest.sim.game import TICK, Game
from rtstest.sim.players import HAZARD_OWNER, STARTING_RESOURCES
from rtstest.sim.units import CREEP, SOLDIER, WORKER, Gather, Move
from rtstest.world.grid import Grid, Terrain
from rtstest.world.mapgen import MapInfo


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
    assert game.train(base.id, SOLDIER)
    _run(game, SOLDIER.train_time + 2)
    assert len(game.units_of(0)) == before
    game.players[0].resources = SOLDIER.cost
    _run(game, SOLDIER.train_time + 1)
    assert len(game.units_of(0)) == before + 1
    assert game.players[0].resources == 0


def test_cancel_refunds_paid_front_only():
    game = _small_game()
    base = game.buildings_of(0)[0]
    game.train(base.id, WORKER)
    game.train(base.id, SOLDIER)
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
