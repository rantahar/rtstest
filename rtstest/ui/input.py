"""Mouse and keyboard handling: selection, orders, panel commands and camera control.

Right-click gives the automatic order (attack, gather, move, or a rally point
for a selected building). Panel buttons and their hotkeys either train units
or start targeting mode, where the next left-click on the map gives that
order and right-click or Esc cancels.
"""

import math

import pygame

from rtstest.sim.game import Game
from rtstest.sim.units import SOLDIER, WORKER, UnitType
from rtstest.ui.panel import Button, Panel, panel_rect, selected_building, selected_units
from rtstest.ui.render import Camera
from rtstest.world.grid import Terrain

EDGE_SCROLL_MARGIN = 6
SCROLL_SPEED = 900
DRAG_THRESHOLD = 5
TRAIN_KEYS = {pygame.K_q: WORKER, pygame.K_w: SOLDIER}


class InputController:
    """Holds the human player's selection and targeting mode; turns input into commands."""

    def __init__(self, game: Game, camera: Camera, panel: Panel, player_id: int) -> None:
        self.game = game
        self.camera = camera
        self.panel = panel
        self.player_id = player_id
        self.selection: set[int] = set()
        self.targeting: str | None = None
        self._drag_start: tuple[int, int] | None = None
        self._drag_now: tuple[int, int] | None = None

    @property
    def _screen_size(self) -> tuple[int, int]:
        return (self.camera.view_w, self.camera.view_h)

    def handle_event(self, event: pygame.event.Event) -> None:
        """React to one pygame event."""
        if event.type == pygame.MOUSEBUTTONDOWN and event.button in (1, 3):
            if panel_rect(self._screen_size).collidepoint(event.pos):
                self._panel_click(event.pos, event.button)
            elif event.button == 1 and self.targeting is not None:
                self._target(event.pos)
            elif event.button == 1:
                self._drag_start = self._drag_now = event.pos
            elif self.targeting is not None:
                self.targeting = None
            else:
                self._command(event.pos)
        elif event.type == pygame.MOUSEMOTION and self._drag_start is not None:
            self._drag_now = event.pos
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self._drag_start is not None:
                self._select(self._drag_start, event.pos)
            self._drag_start = self._drag_now = None
        elif event.type == pygame.MOUSEWHEEL:
            self.camera.zoom(event.y, pygame.mouse.get_pos())
        elif event.type == pygame.KEYDOWN:
            self._hotkey(event.key)

    def cancel_targeting(self) -> bool:
        """Leave targeting mode; False if it was not active."""
        was_targeting = self.targeting is not None
        self.targeting = None
        return was_targeting

    def update(self, dt: float) -> None:
        """Scroll with arrow keys or the screen edge; drop dead units from the selection."""
        keys = pygame.key.get_pressed()
        dx = keys[pygame.K_RIGHT] - keys[pygame.K_LEFT]
        dy = keys[pygame.K_DOWN] - keys[pygame.K_UP]
        if pygame.mouse.get_focused() and self._drag_start is None:
            mx, my = pygame.mouse.get_pos()
            dx += (mx >= self.camera.view_w - EDGE_SCROLL_MARGIN) - (mx < EDGE_SCROLL_MARGIN)
            dy += (my >= self.camera.view_h - EDGE_SCROLL_MARGIN) - (my < EDGE_SCROLL_MARGIN)
        self.camera.pan(dx * SCROLL_SPEED * dt, dy * SCROLL_SPEED * dt)
        self.camera.clamp(self.game.grid.width, self.game.grid.height)
        self.selection = {i for i in self.selection if self.game.entity(i) is not None}
        if not selected_units(self.game, self.player_id, self.selection):
            self.targeting = None

    def drag_rect(self) -> pygame.Rect | None:
        """The selection box on screen while dragging, if any."""
        if self._drag_start is None or not self._is_drag(self._drag_start, self._drag_now):
            return None
        (x0, y0), (x1, y1) = self._drag_start, self._drag_now
        return pygame.Rect(min(x0, x1), min(y0, y1), abs(x1 - x0), abs(y1 - y0))

    @staticmethod
    def _is_drag(a: tuple[int, int], b: tuple[int, int]) -> bool:
        return abs(a[0] - b[0]) > DRAG_THRESHOLD or abs(a[1] - b[1]) > DRAG_THRESHOLD

    def _select(self, start: tuple[int, int], end: tuple[int, int]) -> None:
        if self._is_drag(start, end):
            x0, y0 = self.camera.screen_to_world(*start)
            x1, y1 = self.camera.screen_to_world(*end)
            units = self.game.units_in_rect(x0, y0, x1, y1, self.player_id)
            self.selection = {u.id for u in units}
            return
        e = self.game.entity_at(*self.camera.screen_to_world(*end))
        self.selection = {e.id} if e is not None and e.owner == self.player_id else set()

    def _panel_click(self, pos: tuple[int, int], button: int) -> None:
        """Clicks on the panel: cancel a queue slot (either button) or press a command button."""
        building = selected_building(self.game, self.player_id, self.selection)
        if building is not None and not selected_units(self.game, self.player_id, self.selection):
            index = self.panel.hit_queue(pos, self._screen_size, building)
            if index is not None:
                self.game.cancel_training(building.id, index)
                return
        if button == 1:
            buttons = self.panel.buttons(self.game, self.player_id, self.selection)
            pressed = self.panel.hit_button(pos, self._screen_size, buttons)
            if pressed is not None:
                self._activate(pressed)

    def _hotkey(self, key: int) -> None:
        """A key matching a panel button presses it; with nothing selected, Q/W train at the base."""
        buttons = self.panel.buttons(self.game, self.player_id, self.selection)
        for button in buttons:
            if button.hotkey == key:
                self._activate(button)
                return
        if not buttons and key in TRAIN_KEYS:
            self._train(TRAIN_KEYS[key])

    def _activate(self, button: Button) -> None:
        if button.action == "train":
            self._train(button.unit_type)
        else:
            self.targeting = button.action

    def _target(self, pos: tuple[int, int]) -> None:
        """Give the targeting-mode order at a screen position, then leave targeting mode."""
        action, self.targeting = self.targeting, None
        ids = [u.id for u in selected_units(self.game, self.player_id, self.selection)]
        wx, wy = self.camera.screen_to_world(*pos)
        cell = (math.floor(wx), math.floor(wy))
        if not ids or not self.game.grid.in_bounds(cell):
            return
        if action == "move":
            self.game.order_move(ids, cell)
        elif action == "gather":
            self.game.order_gather(ids, cell)
        elif action == "attack":
            target = self.game.entity_at(wx, wy)
            if target is not None and target.owner != self.player_id:
                self.game.order_attack(ids, target.id)
            else:
                self.game.order_attack_move(ids, cell)

    def _command(self, pos: tuple[int, int]) -> None:
        """Right-click: order selected units, or set selected buildings' rally point."""
        wx, wy = self.camera.screen_to_world(*pos)
        cell = (math.floor(wx), math.floor(wy))
        ids = [u.id for u in selected_units(self.game, self.player_id, self.selection)]
        if not ids:
            for b in self.game.buildings_of(self.player_id):
                if b.id in self.selection:
                    self.game.set_rally(b.id, cell)
            return
        target = self.game.entity_at(wx, wy)
        grid = self.game.grid
        if target is not None and target.owner != self.player_id:
            self.game.order_attack(ids, target.id)
        elif grid.in_bounds(cell) and grid.terrain_at(cell) == Terrain.RESOURCE:
            self.game.order_gather(ids, cell)
        elif grid.in_bounds(cell):
            self.game.order_move(ids, cell)

    def _train(self, utype: UnitType) -> None:
        """Queue at a selected own building, else at the first own building."""
        own = self.game.buildings_of(self.player_id)
        selected = [b for b in own if b.id in self.selection]
        for b in selected or own[:1]:
            self.game.train(b.id, utype)
