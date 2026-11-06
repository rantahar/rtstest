"""A* pathfinding on the square grid.

Paths are lists of cells to walk through, excluding the start cell and
including the final cell. Movement uses 8 neighbours with no corner cutting
(see ``Grid.neighbours``). ``None`` means unreachable.

``find_stand_cell`` picks where a unit should stop near a target: the
nearest unreserved passable cell in rings around it.
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


def ring_cells(targets: Iterable[Cell], ring: int) -> list[Cell]:
    """Cells at Chebyshev distance ``ring`` from the bounding box of ``targets``.

    Ring 0 is the box itself. Cells may be out of bounds.
    """
    xs = [c[0] for c in targets]
    ys = [c[1] for c in targets]
    x0, y0, x1, y1 = min(xs) - ring, min(ys) - ring, max(xs) + ring, max(ys) + ring
    if ring == 0:
        return [(x, y) for y in range(y0, y1 + 1) for x in range(x0, x1 + 1)]
    top = [(x, y0) for x in range(x0, x1 + 1)]
    bottom = [(x, y1) for x in range(x0, x1 + 1)]
    sides = [(x, y) for y in range(y0 + 1, y1) for x in (x0, x1)]
    return top + bottom + sides


def find_stand_cell(grid: Grid, start: Cell, targets: Iterable[Cell], uid: int,
                    min_ring: int = 1, max_ring: int = 1) -> Cell | None:
    """A cell where unit ``uid`` may stop near ``targets``, or None.

    Searches rings around the targets from ``min_ring`` outwards and returns,
    from the first ring with any candidate, the cell nearest to ``start``
    that is passable and not reserved by another unit. Only the ring cells
    are checked, never the unit list.
    """
    targets = list(targets)
    for ring in range(min_ring, max_ring + 1):
        candidates = [c for c in ring_cells(targets, ring) if grid.can_stand(c, uid)]
        if candidates:
            return min(candidates, key=lambda c: octile(c, start))
    return None


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
