"""Tests for A* pathfinding."""

from rtstest.world.grid import Grid, Terrain, chebyshev
from rtstest.world.pathfinding import find_path, find_path_adjacent, find_stand_cell, ring_cells


def _wall(height_gap: bool) -> Grid:
    """10x10 grid with a rock wall at x=5, open at the bottom row if height_gap."""
    g = Grid(10, 10)
    for y in range(9 if height_gap else 10):
        g.set_terrain((5, y), Terrain.ROCK)
    return g


def _is_connected(start, path):
    prev = start
    for c in path:
        if chebyshev(prev, c) != 1:
            return False
        prev = c
    return True


def test_straight_line():
    assert find_path(Grid(10, 10), (0, 0), (4, 0)) == [(1, 0), (2, 0), (3, 0), (4, 0)]


def test_already_there():
    assert find_path(Grid(3, 3), (1, 1), (1, 1)) == []


def test_around_wall():
    g = _wall(height_gap=True)
    path = find_path(g, (2, 2), (8, 2))
    assert path is not None and path[-1] == (8, 2)
    assert (5, 9) in path
    assert all(g.is_passable(c) for c in path)
    assert _is_connected((2, 2), path)


def test_no_path():
    assert find_path(_wall(height_gap=False), (2, 2), (8, 2)) is None


def test_impassable_goal():
    g = Grid(5, 5)
    g.set_terrain((3, 3), Terrain.WATER)
    assert find_path(g, (0, 0), (3, 3)) is None


def test_no_corner_cutting():
    g = Grid(3, 3)
    g.set_terrain((1, 0), Terrain.ROCK)
    g.set_terrain((0, 1), Terrain.ROCK)
    assert find_path(g, (0, 0), (1, 1)) is None


def test_adjacent_to_impassable_target():
    g = Grid(10, 10)
    g.set_terrain((5, 5), Terrain.RESOURCE)
    path = find_path_adjacent(g, (0, 0), [(5, 5)])
    assert path and chebyshev(path[-1], (5, 5)) == 1
    assert _is_connected((0, 0), path)


def test_adjacent_already_next_to_target():
    g = Grid(5, 5)
    g.set_terrain((2, 2), Terrain.RESOURCE)
    assert find_path_adjacent(g, (1, 1), [(2, 2)]) == []


def test_stand_cell_nearest_free_in_ring():
    g = Grid(10, 10)
    assert find_stand_cell(g, (0, 5), [(5, 5)], uid=1) == (4, 5)
    g.reserve((4, 5), 2)
    assert find_stand_cell(g, (0, 5), [(5, 5)], uid=1) in {(4, 4), (4, 6)}
    assert find_stand_cell(g, (0, 5), [(5, 5)], uid=2) == (4, 5)


def test_stand_cell_ring_zero_and_outer_rings():
    g = Grid(10, 10)
    assert find_stand_cell(g, (0, 0), [(5, 5)], uid=1, min_ring=0, max_ring=2) == (5, 5)
    for c in ring_cells([(5, 5)], 1):
        g.reserve(c, 99)
    stand = find_stand_cell(g, (0, 0), [(5, 5)], uid=1, min_ring=1, max_ring=2)
    assert stand is not None and chebyshev(stand, (5, 5)) == 2
    assert find_stand_cell(g, (0, 0), [(5, 5)], uid=1) is None
