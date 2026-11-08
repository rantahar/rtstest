"""Camera: integer-pixel view onto the world, with pan, zoom and edge clamping."""

from rtstest.world import Grid

__all__ = ["Camera"]

DEFAULT_TILE = 32
MIN_TILE = 16
MAX_TILE = 64
ZOOM_STEP = 8
EDGE_MARGIN_TILES = 2


class Camera:
    """Integer-pixel view onto the world; world coordinates are in cells.

    ``insets`` are the (top, bottom) pixel heights covered by HUD and panel;
    clamping keeps every map row scrollable into the uncovered area.
    """

    def __init__(self, view_size: tuple[int, int], tile: int = DEFAULT_TILE,
                 insets: tuple[int, int] = (0, 0)) -> None:
        self.view_w, self.view_h = view_size
        self.tile = tile
        self.insets = insets
        self.ox = 0
        self.oy = 0

    def resize(self, view_size: tuple[int, int]) -> None:
        self.view_w, self.view_h = view_size

    def world_to_screen(self, wx: float, wy: float) -> tuple[int, int]:
        return (round(wx * self.tile) - self.ox, round(wy * self.tile) - self.oy)

    def screen_to_world(self, sx: float, sy: float) -> tuple[float, float]:
        return ((sx + self.ox) / self.tile, (sy + self.oy) / self.tile)

    def center_on(self, wx: float, wy: float) -> None:
        self.ox = round(wx * self.tile - self.view_w / 2)
        self.oy = round(wy * self.tile - self.view_h / 2)

    def pan(self, dx: float, dy: float) -> None:
        """Move the view by a number of pixels."""
        self.ox += round(dx)
        self.oy += round(dy)

    def zoom(self, steps: int, anchor: tuple[int, int]) -> None:
        """Change tile size by ``steps`` zoom steps, keeping ``anchor`` fixed on screen."""
        wx, wy = self.screen_to_world(*anchor)
        self.tile = max(MIN_TILE, min(MAX_TILE, self.tile + steps * ZOOM_STEP))
        self.ox = round(wx * self.tile - anchor[0])
        self.oy = round(wy * self.tile - anchor[1])

    def clamp(self, world_w: int, world_h: int) -> None:
        """Keep the view near the map: at most a small margin past each edge."""
        margin = EDGE_MARGIN_TILES * self.tile
        self.ox = _clamp_axis(self.ox, world_w * self.tile, self.view_w, margin, (0, 0))
        self.oy = _clamp_axis(self.oy, world_h * self.tile, self.view_h, margin, self.insets)

    def visible_cells(self, grid: Grid) -> tuple[int, int, int, int]:
        """Cell range ``(x0, y0, x1, y1)``, end-exclusive, that is on screen."""
        x0 = max(0, self.ox // self.tile)
        y0 = max(0, self.oy // self.tile)
        x1 = min(grid.width, (self.ox + self.view_w) // self.tile + 1)
        y1 = min(grid.height, (self.oy + self.view_h) // self.tile + 1)
        return x0, y0, x1, y1


def _clamp_axis(offset: int, world_px: int, view_px: int, margin: int,
                insets: tuple[int, int]) -> int:
    lo, hi = insets
    visible = view_px - lo - hi
    if world_px + 2 * margin <= visible:
        return (world_px - visible) // 2 - lo
    return max(-margin - lo, min(world_px - view_px + hi + margin, offset))
