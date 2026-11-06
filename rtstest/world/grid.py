"""Square tile grid: terrain, resource stocks and building occupancy.

Cells are ``(x, y)`` integer tuples with ``(0, 0)`` at the top-left. Only
grass cells not covered by a building are passable; units never block cells.
A unit may reserve one cell as the place it will stop on (to work, attack or
wait); a reservation does not block movement, only other units stopping there.
"""

from collections.abc import Iterable, Iterator
from enum import IntEnum

Cell = tuple[int, int]

DEFAULT_RESOURCE_AMOUNT = 150
DIAGONAL_COST = 2 ** 0.5
_ORTHOGONAL = ((1, 0), (-1, 0), (0, 1), (0, -1))
_DIAGONAL = ((1, 1), (1, -1), (-1, 1), (-1, -1))


def chebyshev(a: Cell, b: Cell) -> int:
    """Grid distance where diagonal steps count as one."""
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


class Terrain(IntEnum):
    """Kind of a tile. Only GRASS is walkable; RESOURCE is harvested from beside it."""

    GRASS = 0
    ROCK = 1
    WATER = 2
    RESOURCE = 3


class Grid:
    """A width x height map of terrain tiles with resource stocks and occupancy."""

    def __init__(self, width: int, height: int) -> None:
        self.width = width
        self.height = height
        self._terrain = [[Terrain.GRASS] * width for _ in range(height)]
        self._resources: dict[Cell, int] = {}
        self._occupied: set[Cell] = set()
        self._reserved: dict[Cell, int] = {}

    def in_bounds(self, cell: Cell) -> bool:
        """Whether the cell lies inside the map."""
        x, y = cell
        return 0 <= x < self.width and 0 <= y < self.height

    def terrain_at(self, cell: Cell) -> Terrain:
        """Terrain of an in-bounds cell."""
        return self._terrain[cell[1]][cell[0]]

    def set_terrain(self, cell: Cell, terrain: Terrain,
                    amount: int = DEFAULT_RESOURCE_AMOUNT) -> None:
        """Set a cell's terrain; a RESOURCE cell gets ``amount`` units of stock."""
        self._terrain[cell[1]][cell[0]] = terrain
        if terrain == Terrain.RESOURCE:
            self._resources[cell] = amount
        else:
            self._resources.pop(cell, None)

    def resource_amount(self, cell: Cell) -> int:
        """Stock left in a resource cell (0 for other cells)."""
        return self._resources.get(cell, 0)

    def resource_cells(self) -> list[Cell]:
        """All cells that still hold resources."""
        return list(self._resources)

    def take_resource(self, cell: Cell, amount: int) -> int:
        """Remove up to ``amount`` from a cell's stock and return what was taken.

        A depleted cell turns into grass.
        """
        stock = self._resources.get(cell, 0)
        taken = min(stock, amount)
        if stock - taken <= 0:
            if stock > 0:
                self.set_terrain(cell, Terrain.GRASS)
        else:
            self._resources[cell] = stock - taken
        return taken

    def is_occupied(self, cell: Cell) -> bool:
        """Whether a building covers the cell."""
        return cell in self._occupied

    def occupy(self, cells: Iterable[Cell]) -> None:
        """Mark cells as covered by a building."""
        self._occupied.update(cells)

    def release(self, cells: Iterable[Cell]) -> None:
        """Mark cells as no longer covered by a building."""
        self._occupied.difference_update(cells)

    def reserved_by(self, cell: Cell) -> int | None:
        """Id of the unit that reserved the cell as its stopping place, if any."""
        return self._reserved.get(cell)

    def can_stand(self, cell: Cell, uid: int) -> bool:
        """Whether unit ``uid`` may stop on the cell: passable and not reserved by another unit."""
        return self.is_passable(cell) and self._reserved.get(cell, uid) == uid

    def reserve(self, cell: Cell, uid: int) -> bool:
        """Reserve a cell for unit ``uid``; False if another unit holds it."""
        if self._reserved.get(cell, uid) != uid:
            return False
        self._reserved[cell] = uid
        return True

    def unreserve(self, cell: Cell, uid: int) -> None:
        """Drop unit ``uid``'s reservation of a cell (no-op if it does not hold it)."""
        if self._reserved.get(cell) == uid:
            del self._reserved[cell]

    def is_passable(self, cell: Cell) -> bool:
        """Whether a unit may stand on the cell."""
        return (self.in_bounds(cell)
                and self.terrain_at(cell) == Terrain.GRASS
                and cell not in self._occupied)

    def adjacent_cells(self, cell: Cell) -> list[Cell]:
        """The up to 8 in-bounds cells around a cell, passable or not."""
        x, y = cell
        return [(x + dx, y + dy) for dx, dy in _ORTHOGONAL + _DIAGONAL
                if self.in_bounds((x + dx, y + dy))]

    def neighbours(self, cell: Cell) -> Iterator[tuple[Cell, float]]:
        """Passable cells reachable in one step, with step cost.

        Diagonal steps are allowed only when both orthogonal cells beside the
        step are passable (no cutting corners).
        """
        x, y = cell
        for dx, dy in _ORTHOGONAL:
            n = (x + dx, y + dy)
            if self.is_passable(n):
                yield n, 1.0
        for dx, dy in _DIAGONAL:
            n = (x + dx, y + dy)
            if (self.is_passable(n) and self.is_passable((x + dx, y))
                    and self.is_passable((x, y + dy))):
                yield n, DIAGONAL_COST
