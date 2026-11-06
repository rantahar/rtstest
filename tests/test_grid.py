"""Tests for the tile grid and map generation."""

from rtstest.world.grid import Grid, Terrain, chebyshev
from rtstest.world.mapgen import generate


def test_take_resource_depletes_to_grass():
    g = Grid(5, 5)
    g.set_terrain((2, 2), Terrain.RESOURCE, amount=3)
    assert not g.is_passable((2, 2))
    assert g.take_resource((2, 2), 2) == 2
    assert g.resource_amount((2, 2)) == 1
    assert g.take_resource((2, 2), 5) == 1
    assert g.terrain_at((2, 2)) == Terrain.GRASS
    assert g.is_passable((2, 2))
    assert g.resource_cells() == []


def test_occupy_and_release():
    g = Grid(5, 5)
    g.occupy([(1, 1), (1, 2)])
    assert not g.is_passable((1, 1))
    g.release([(1, 1)])
    assert g.is_passable((1, 1))
    assert not g.is_passable((1, 2))


def test_neighbours_do_not_cut_corners():
    g = Grid(3, 3)
    g.set_terrain((1, 0), Terrain.ROCK)
    cells = {c for c, _ in g.neighbours((0, 0))}
    assert cells == {(0, 1)}


def test_mapgen_is_deterministic():
    a, b = generate(40, 40, 3, seed=7), generate(40, 40, 3, seed=7)
    assert a.starts == b.starts
    cells = [(x, y) for y in range(40) for x in range(40)]
    assert all(a.grid.terrain_at(c) == b.grid.terrain_at(c) for c in cells)


def test_mapgen_starts_have_room_and_resources():
    info = generate(64, 64, 4, seed=3)
    for s in info.starts:
        base = [(s[0] + dx, s[1] + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1)]
        assert all(info.grid.is_passable(c) for c in base)
        assert any(chebyshev(r, s) <= 10 for r in info.grid.resource_cells())


def test_reservations():
    g = Grid(5, 5)
    assert g.reserve((1, 1), 7)
    assert g.reserved_by((1, 1)) == 7
    assert g.can_stand((1, 1), 7) and not g.can_stand((1, 1), 8)
    assert not g.reserve((1, 1), 8)
    assert g.is_passable((1, 1))
    g.unreserve((1, 1), 8)
    assert g.reserved_by((1, 1)) == 7
    g.unreserve((1, 1), 7)
    assert g.reserved_by((1, 1)) is None
