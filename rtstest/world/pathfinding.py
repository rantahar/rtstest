"""A* pathfinding on the square grid.

Paths are lists of cells to walk through, excluding the start cell and
including the final cell. Movement uses 8 neighbours with no corner cutting
(see ``Grid.neighbours``). ``None`` means unreachable.
"""

import heapq
import itertools
from collections.abc import Callable, Iterable

from rtstest.world.grid import DIAGONAL_COST, Cell, Grid

MAX_EXPANSIONS = 20000


def octile(a: Cell, b: Cell) -> float:
    """Shortest 8-direction distance between two cells on an empty grid."""
    dx, dy = abs(a[0] - b[0]), abs(a[1] - b[1])
    return max(dx, dy) + (DIAGONAL_COST - 1) * min(dx, dy)


def find_path(grid: Grid, start: Cell, goal: Cell,
              max_expansions: int = MAX_EXPANSIONS) -> list[Cell] | None:
    """Shortest path from ``start`` to a passable ``goal``; ``[]`` if already there."""
    if start == goal:
        return []
    if not grid.is_passable(goal):
        return None
    return _astar(grid, start, lambda c: c == goal,
                  lambda c: octile(c, goal), max_expansions)


def find_path_adjacent(grid: Grid, start: Cell, targets: Iterable[Cell],
                       max_expansions: int = MAX_EXPANSIONS) -> list[Cell] | None:
    """Shortest path to any passable cell on or next to one of ``targets``.

    Targets may be impassable (resources, building footprints). Returns ``[]``
    when ``start`` already qualifies.
    """
    goals = set()
    for t in targets:
        for c in [t, *grid.adjacent_cells(t)]:
            if c == start or grid.is_passable(c):
                goals.add(c)
    if not goals:
        return None
    if start in goals:
        return []
    goal_list = list(goals)
    return _astar(grid, start, goals.__contains__,
                  lambda c: min(octile(c, g) for g in goal_list), max_expansions)


def _astar(grid: Grid, start: Cell, is_goal: Callable[[Cell], bool],
           heuristic: Callable[[Cell], float], max_expansions: int) -> list[Cell] | None:
    """Generic A* search; returns the path excluding ``start``, or None."""
    counter = itertools.count()
    open_heap = [(heuristic(start), next(counter), start)]
    g_cost = {start: 0.0}
    came_from: dict[Cell, Cell] = {}
    closed = set()
    while open_heap and len(closed) < max_expansions:
        _, _, cell = heapq.heappop(open_heap)
        if cell in closed:
            continue
        if is_goal(cell):
            path = []
            while cell != start:
                path.append(cell)
                cell = came_from[cell]
            path.reverse()
            return path
        closed.add(cell)
        for n, step in grid.neighbours(cell):
            g = g_cost[cell] + step
            if g < g_cost.get(n, float("inf")):
                g_cost[n] = g
                came_from[n] = cell
                heapq.heappush(open_heap, (g + heuristic(n), next(counter), n))
    return None
