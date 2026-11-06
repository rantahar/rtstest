"""Pygame rendering: the camera, map tiles, buildings, units, top HUD and lower panel."""

import pygame

from rtstest.sim import HAZARD_OWNER, BuildingType, Game
from rtstest.ui.assets import SpriteCache
from rtstest.ui.panel import Panel
from rtstest.world import Cell, Grid, Terrain

__all__ = ["Camera", "Renderer", "HUD_HEIGHT"]

DEFAULT_TILE = 32
MIN_TILE = 16
MAX_TILE = 64
ZOOM_STEP = 8
EDGE_MARGIN_TILES = 2
UNIT_SPRITE_SCALE = 0.8
HUD_HEIGHT = 26
FONT_SIZE = 22

BACKGROUND = (12, 12, 16)
TERRAIN_COLORS = {Terrain.GRASS: (66, 104, 58), Terrain.ROCK: (112, 106, 98),
                  Terrain.WATER: (38, 68, 128), Terrain.RESOURCE: (66, 104, 58)}
SELECT_COLOR = (240, 240, 120)
HP_BACK = (40, 0, 0)
HP_FRONT = (90, 220, 90)
CARRY_COLOR = (120, 230, 240)
BUILD_COLOR = (240, 170, 60)
GHOST_OK = (90, 230, 90)
GHOST_BAD = (230, 70, 70)
UNFINISHED_ALPHA = 130
HUD_BG = (20, 20, 28)
TEXT_COLOR = (230, 230, 230)
OVERLAY_COLOR = (0, 0, 0, 160)


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


class Renderer:
    """Draws one frame of the game to a pygame surface."""

    def __init__(self, screen: pygame.Surface) -> None:
        self.screen = screen
        self.sprites = SpriteCache()
        self.font = pygame.font.Font(None, FONT_SIZE)
        self.panel = Panel(self.sprites, self.font)

    def draw(self, game: Game, camera: Camera, player_id: int,
             selection: set[int], drag_rect: pygame.Rect | None,
             targeting: str | None = None, menu: str | None = None,
             ghost: tuple[BuildingType, Cell, bool] | None = None) -> None:
        """Draw the map, entities, placement ghost, selection box, HUD and lower panel."""
        self.screen.fill(BACKGROUND)
        self._draw_tiles(game, camera)
        self._draw_buildings(game, camera, selection)
        self._draw_units(game, camera, selection)
        if ghost is not None:
            self._draw_ghost(game, camera, player_id, *ghost)
        if drag_rect is not None:
            pygame.draw.rect(self.screen, SELECT_COLOR, drag_rect, 1)
        self.panel.draw(self.screen, game, player_id, selection, targeting, menu)
        self._draw_hud(game, player_id, selection)

    def _draw_tiles(self, game: Game, camera: Camera) -> None:
        t = camera.tile
        resource = self.sprites.get("resource", (t, t))
        x0, y0, x1, y1 = camera.visible_cells(game.grid)
        for y in range(y0, y1):
            for x in range(x0, x1):
                terrain = game.grid.terrain_at((x, y))
                sx, sy = camera.world_to_screen(x, y)
                self.screen.fill(TERRAIN_COLORS[terrain], (sx, sy, t, t))
                if terrain == Terrain.RESOURCE:
                    self.screen.blit(resource, (sx, sy))

    def _draw_buildings(self, game: Game, camera: Camera, selection: set[int]) -> None:
        t = camera.tile
        for b in game.buildings.values():
            w, h = b.type.size
            sx, sy = camera.world_to_screen(*b.cell)
            color = game.players[b.owner].color
            sprite = self.sprites.get(b.type.name, (w * t, h * t), color)
            if not b.complete:
                sprite = sprite.copy()
                sprite.set_alpha(UNFINISHED_ALPHA)
            self.screen.blit(sprite, (sx, sy))
            rect = pygame.Rect(sx, sy, w * t, h * t)
            if not b.complete:
                pygame.draw.rect(self.screen, BUILD_COLOR,
                                 (rect.left, rect.bottom + 2,
                                  round(rect.width * b.build_fraction), 3))
            if b.id in selection:
                pygame.draw.rect(self.screen, SELECT_COLOR, rect, 2)
                if b.rally is not None:
                    rx, ry = camera.world_to_screen(b.rally[0] + 0.5, b.rally[1] + 0.5)
                    pygame.draw.line(self.screen, SELECT_COLOR, rect.center, (rx, ry), 1)
                    pygame.draw.circle(self.screen, SELECT_COLOR, (rx, ry), 5, 2)
            self._hp_bar(rect.left, rect.top - 6, rect.width, b.hp / b.max_hp)
            if b.queue:
                frac = b.training_fraction
                pygame.draw.rect(self.screen, CARRY_COLOR,
                                 (rect.left, rect.bottom + 2, round(rect.width * frac), 3))

    def _draw_ghost(self, game: Game, camera: Camera, player_id: int,
                    btype: BuildingType, cell: Cell, valid: bool) -> None:
        """Translucent footprint of a building being placed, outlined green or red."""
        t = camera.tile
        w, h = btype.size
        sx, sy = camera.world_to_screen(*cell)
        sprite = self.sprites.get(btype.name, (w * t, h * t), game.players[player_id].color).copy()
        sprite.set_alpha(UNFINISHED_ALPHA)
        self.screen.blit(sprite, (sx, sy))
        pygame.draw.rect(self.screen, GHOST_OK if valid else GHOST_BAD, (sx, sy, w * t, h * t), 2)

    def _draw_units(self, game: Game, camera: Camera, selection: set[int]) -> None:
        size = max(4, round(camera.tile * UNIT_SPRITE_SCALE))
        for u in game.units.values():
            tint = None if u.owner == HAZARD_OWNER else game.players[u.owner].color
            sprite = self.sprites.get(u.type.name, (size, size), tint)
            cx, cy = camera.world_to_screen(u.x, u.y)
            rect = sprite.get_rect(center=(cx, cy))
            if u.id in selection:
                pygame.draw.ellipse(self.screen, SELECT_COLOR, rect.inflate(4, 4), 2)
            self.screen.blit(sprite, rect)
            if u.id in selection or u.hp < u.max_hp:
                self._hp_bar(rect.left, rect.top - 5, rect.width, u.hp / u.max_hp)
            if u.carrying:
                pygame.draw.circle(self.screen, CARRY_COLOR, rect.topright, 3)

    def _hp_bar(self, x: int, y: int, width: int, frac: float) -> None:
        self.screen.fill(HP_BACK, (x, y, width, 3))
        self.screen.fill(HP_FRONT, (x, y, round(width * max(0.0, frac)), 3))

    def _draw_hud(self, game: Game, player_id: int, selection: set[int]) -> None:
        sw, sh = self.screen.get_size()
        player = game.players[player_id]
        minutes, seconds = divmod(int(game.time), 60)
        next_wave = int(game.next_wave_in)
        top = (f"Resources {player.resources}   Time {minutes:02d}:{seconds:02d}   "
               f"Wave {game.wave}   next in {next_wave}s   Selected {len(selection)}")
        self.screen.fill(HUD_BG, (0, 0, sw, HUD_HEIGHT))
        self.screen.blit(self.font.render(top, True, TEXT_COLOR), (8, 5))
        x = sw - 8
        for p in reversed(game.players):
            label = self.font.render(p.name if p.alive else f"{p.name} †", True, p.color)
            x -= label.get_width() + 12
            self.screen.blit(label, (x, 5))
        if not player.alive:
            overlay = pygame.Surface((sw, sh), pygame.SRCALPHA)
            overlay.fill(OVERLAY_COLOR)
            self.screen.blit(overlay, (0, 0))
            text = self.font.render(f"You did not survive. Time {minutes:02d}:{seconds:02d}",
                                    True, TEXT_COLOR)
            self.screen.blit(text, text.get_rect(center=(sw // 2, sh // 2)))
