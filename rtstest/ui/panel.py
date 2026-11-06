"""Lower command panel: selection info, a building's training queue and command buttons.

The panel covers the bottom ``PANEL_HEIGHT`` pixels of the window, in the
style of SC2: info on the left, the selected building's queue in the middle,
a 4x3 button grid on the right. Each button sits in a fixed grid slot and
its hotkey is the key at the same position on the keyboard (``GRID_KEYS``:
QWER / ASDF / ZXCV). ``Panel.buttons`` lists what the selection can do;
workers have a Build button (Z) that opens the build menu (``menu="build"``)
listing ``BUILDABLE`` buildings plus Back (V). ``InputController`` handles
clicks and hotkeys, ``Panel.draw`` draws it.
"""

from dataclasses import dataclass

import pygame

from rtstest.sim.buildings import BUILDABLE, MAX_QUEUE, Building, BuildingType
from rtstest.sim.game import Game
from rtstest.sim.units import SOLDIER, WORKER, Unit, UnitType
from rtstest.ui.assets import SpriteCache

PANEL_HEIGHT = 160
INFO_WIDTH = 300
PAD = 10
BUTTON_SIZE = 42
BUTTON_GAP = 6
BUTTON_COLS = 4
GRID_KEYS = (pygame.K_q, pygame.K_w, pygame.K_e, pygame.K_r,
             pygame.K_a, pygame.K_s, pygame.K_d, pygame.K_f,
             pygame.K_z, pygame.K_x, pygame.K_c, pygame.K_v)
QUEUE_ICON = 40
QUEUE_GAP = 6
LINE_HEIGHT = 18

PANEL_BG = (24, 26, 34)
PANEL_BORDER = (70, 74, 90)
BUTTON_BG = (40, 44, 58)
BUTTON_ACTIVE = (240, 240, 120)
TEXT_COLOR = (230, 230, 230)
DIM_TEXT = (150, 150, 160)
WARN_TEXT = (240, 120, 100)
PROGRESS_COLOR = (120, 230, 240)
HELP_LINES = ("LMB select / drag box    RMB move, gather, attack, rally, resume build",
              "Arrows / screen edge scroll    wheel zoom    Esc quit")


@dataclass(frozen=True)
class Button:
    """One command in grid ``slot``.

    Actions: ``train`` a unit type, ``place`` a building type, open the
    ``build`` menu, go ``back`` from it, or start targeting for a unit action
    (``move``, ``attack``, ``gather``).
    """

    action: str
    label: str
    slot: int
    icon: str
    unit_type: UnitType | None = None
    building_type: BuildingType | None = None

    @property
    def cost(self) -> int | None:
        """Resource cost shown on the button, if any."""
        if self.unit_type is not None:
            return self.unit_type.cost
        if self.building_type is not None:
            return self.building_type.cost
        return None

    @property
    def hotkey(self) -> int:
        """The grid key at this button's slot."""
        return GRID_KEYS[self.slot]


TRAIN_SLOTS = {WORKER.name: 0, SOLDIER.name: 1}
MOVE_BUTTON = Button("move", "Move", 0, "move")
ATTACK_BUTTON = Button("attack", "Attack", 4, "attack")
GATHER_BUTTON = Button("gather", "Gather", 5, "resource")
BUILD_BUTTON = Button("build", "Build", 8, "build")
BACK_BUTTON = Button("back", "Back", 11, "back")


def selected_units(game: Game, player_id: int, selection: set[int]) -> list[Unit]:
    """The player's own units in the selection."""
    return [game.units[i] for i in selection
            if i in game.units and game.units[i].owner == player_id]


def selected_building(game: Game, player_id: int, selection: set[int]) -> Building | None:
    """The player's own selected building, if the selection holds one."""
    for i in selection:
        b = game.buildings.get(i)
        if b is not None and b.owner == player_id:
            return b
    return None


def panel_rect(size: tuple[int, int]) -> pygame.Rect:
    """Screen area of the panel for a window of ``size``."""
    return pygame.Rect(0, size[1] - PANEL_HEIGHT, size[0], PANEL_HEIGHT)


class Panel:
    """Lays out, hit-tests and draws the lower panel."""

    def __init__(self, sprites: SpriteCache, font: pygame.font.Font) -> None:
        self.sprites = sprites
        self.font = font
        self.small = pygame.font.Font(None, 16)

    def buttons(self, game: Game, player_id: int, selection: set[int],
                menu: str | None = None) -> list[Button]:
        """Buttons for the selection.

        Own units: unit actions, or the build menu when ``menu == "build"``
        and workers are selected. Otherwise the selected complete building's
        train buttons.
        """
        units = selected_units(game, player_id, selection)
        if units:
            workers = any(u.type.gather_capacity for u in units)
            if menu == "build" and workers:
                return [Button("place", b.name.capitalize(), i, b.name, building_type=b)
                        for i, b in enumerate(BUILDABLE)] + [BACK_BUTTON]
            buttons = [MOVE_BUTTON, ATTACK_BUTTON]
            if workers:
                buttons += [GATHER_BUTTON, BUILD_BUTTON]
            return buttons
        building = selected_building(game, player_id, selection)
        if building is None or not building.complete:
            return []
        return [Button("train", t.name.capitalize(), TRAIN_SLOTS.get(t.name, i), t.name, t)
                for i, t in enumerate(building.type.trains)]

    @staticmethod
    def button_rect(size: tuple[int, int], slot: int) -> pygame.Rect:
        """Screen rect of a grid slot."""
        top = panel_rect(size).top + PAD
        left = size[0] - PAD - BUTTON_COLS * (BUTTON_SIZE + BUTTON_GAP) + BUTTON_GAP
        return pygame.Rect(left + (slot % BUTTON_COLS) * (BUTTON_SIZE + BUTTON_GAP),
                           top + (slot // BUTTON_COLS) * (BUTTON_SIZE + BUTTON_GAP),
                           BUTTON_SIZE, BUTTON_SIZE)

    @staticmethod
    def queue_rects(size: tuple[int, int]) -> list[pygame.Rect]:
        """Screen rects of the ``MAX_QUEUE`` queue slots."""
        top = panel_rect(size).top + PAD + LINE_HEIGHT
        return [pygame.Rect(INFO_WIDTH + PAD + i * (QUEUE_ICON + QUEUE_GAP), top,
                            QUEUE_ICON, QUEUE_ICON) for i in range(MAX_QUEUE)]

    def hit_button(self, pos: tuple[int, int], size: tuple[int, int],
                   buttons: list[Button]) -> Button | None:
        """The button under a screen position."""
        for button in buttons:
            if self.button_rect(size, button.slot).collidepoint(pos):
                return button
        return None

    def hit_queue(self, pos: tuple[int, int], size: tuple[int, int],
                  building: Building) -> int | None:
        """Index of the occupied queue slot under a screen position."""
        for i, rect in enumerate(self.queue_rects(size)[:len(building.queue)]):
            if rect.collidepoint(pos):
                return i
        return None

    def draw(self, screen: pygame.Surface, game: Game, player_id: int,
             selection: set[int], targeting: str | None, menu: str | None = None) -> None:
        """Draw the whole panel; ``targeting`` is an action name or ``"place"``."""
        size = screen.get_size()
        rect = panel_rect(size)
        screen.fill(PANEL_BG, rect)
        pygame.draw.line(screen, PANEL_BORDER, rect.topleft, rect.topright, 2)
        building = selected_building(game, player_id, selection)
        self._draw_info(screen, rect, game, player_id, selection, building, targeting)
        if (building is not None and building.complete
                and not selected_units(game, player_id, selection)):
            self._draw_queue(screen, size, game, building)
        self._draw_buttons(screen, size, game, player_id, selection, targeting, menu)

    def _text(self, screen: pygame.Surface, text: str, pos: tuple[int, int],
              color=TEXT_COLOR, font: pygame.font.Font | None = None) -> None:
        screen.blit((font or self.font).render(text, True, color), pos)

    def _draw_info(self, screen, rect, game, player_id, selection, building, targeting) -> None:
        x, y = rect.left + PAD, rect.top + PAD
        lines: list[tuple[str, tuple[int, int, int]]] = []
        if targeting == "place":
            lines.append(("Place building: left-click site, right-click / Esc cancel",
                          BUTTON_ACTIVE))
        elif targeting is not None:
            lines.append((f"{targeting.capitalize()}: left-click target, "
                          "right-click / Esc cancel", BUTTON_ACTIVE))
        units = selected_units(game, player_id, selection)
        if len(units) == 1:
            u = units[0]
            lines.append((u.type.name.capitalize(), TEXT_COLOR))
            lines.append((f"HP {max(0, round(u.hp))} / {u.max_hp}", DIM_TEXT))
            if u.carrying:
                lines.append((f"Carrying {u.carrying}", DIM_TEXT))
        elif units:
            counts: dict[str, int] = {}
            for u in units:
                counts[u.type.name] = counts.get(u.type.name, 0) + 1
            lines.append((f"{len(units)} units", TEXT_COLOR))
            lines.append(("  ".join(f"{n} {name}" for name, n in counts.items()), DIM_TEXT))
        elif building is not None:
            lines.append((building.type.name.capitalize(), TEXT_COLOR))
            lines.append((f"HP {max(0, round(building.hp))} / {building.max_hp}", DIM_TEXT))
            if building.complete:
                lines.append(("RMB sets rally point", DIM_TEXT))
            else:
                lines.append((f"Under construction {round(building.build_fraction * 100)}%",
                              WARN_TEXT))
                lines.append(("RMB with a worker on it to continue building", DIM_TEXT))
        else:
            lines.extend((line, DIM_TEXT) for line in HELP_LINES)
        for i, (text, color) in enumerate(lines):
            self._text(screen, text, (x, y + i * LINE_HEIGHT), color)

    def _draw_queue(self, screen, size, game, building) -> None:
        rects = self.queue_rects(size)
        self._text(screen, "Queue (click to cancel)", (rects[0].left, rects[0].top - LINE_HEIGHT),
                   DIM_TEXT)
        color = game.players[building.owner].color
        for i, rect in enumerate(rects):
            pygame.draw.rect(screen, BUTTON_BG, rect)
            pygame.draw.rect(screen, PANEL_BORDER, rect, 1)
            if i >= len(building.queue):
                continue
            utype = building.queue[i]
            icon = self.sprites.get(utype.name, (QUEUE_ICON - 6, QUEUE_ICON - 6), color)
            screen.blit(icon, icon.get_rect(center=rect.center))
        if building.queue:
            front = rects[0]
            if building.paid:
                frac = min(1.0, building.progress / building.queue[0].train_time)
                screen.fill(PROGRESS_COLOR, (front.left, front.bottom + 3,
                                             round(front.width * frac), 4))
            else:
                self._text(screen, "Waiting for resources", (front.left, front.bottom + 3),
                           WARN_TEXT, self.small)

    def _draw_buttons(self, screen, size, game, player_id, selection, targeting, menu) -> None:
        buttons = self.buttons(game, player_id, selection, menu)
        color = game.players[player_id].color
        resources = game.players[player_id].resources
        for button in buttons:
            rect = self.button_rect(size, button.slot)
            pygame.draw.rect(screen, BUTTON_BG, rect)
            active = button.action == targeting
            pygame.draw.rect(screen, BUTTON_ACTIVE if active else PANEL_BORDER, rect,
                             2 if active else 1)
            tint = color if button.unit_type or button.building_type else None
            icon = self.sprites.get(button.icon, (BUTTON_SIZE - 12, BUTTON_SIZE - 12), tint)
            screen.blit(icon, icon.get_rect(center=rect.center))
            self._text(screen, pygame.key.name(button.hotkey).upper(),
                       (rect.left + 3, rect.top + 2), TEXT_COLOR, self.small)
            cost = button.cost
            if cost is not None:
                label = self.small.render(str(cost), True,
                                          TEXT_COLOR if resources >= cost else WARN_TEXT)
                screen.blit(label, label.get_rect(bottomright=(rect.right - 3, rect.bottom - 2)))
