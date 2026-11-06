"""Sprite loading: placeholder SVGs rendered at a requested size, optionally tinted.

Sprites live in the package's ``assets/sprites`` folder as ``<name>.svg``,
where the name matches the unit or building type name. Light parts of a
sprite take the owner's colour through multiplicative tinting. A missing or
unreadable sprite becomes a magenta square instead of an error.
"""

from importlib import resources

import pygame

__all__ = ["SpriteCache"]

SPRITE_DIR = resources.files("rtstest") / "assets" / "sprites"
MISSING_COLOR = (255, 0, 255)

Color = tuple[int, int, int]


class SpriteCache:
    """Loads each (name, size, tint) combination once."""

    def __init__(self) -> None:
        self._cache: dict[tuple[str, tuple[int, int], Color | None], pygame.Surface] = {}

    def get(self, name: str, size: tuple[int, int], tint: Color | None = None) -> pygame.Surface:
        """The sprite ``name`` rendered at ``size`` pixels, tinted if requested."""
        key = (name, size, tint)
        surface = self._cache.get(key)
        if surface is None:
            surface = self._load(name, size)
            if tint is not None:
                surface.fill((*tint, 255), special_flags=pygame.BLEND_RGBA_MULT)
            self._cache[key] = surface
        return surface

    def _load(self, name: str, size: tuple[int, int]) -> pygame.Surface:
        try:
            with resources.as_file(SPRITE_DIR / f"{name}.svg") as path:
                if hasattr(pygame.image, "load_sized_svg"):
                    surface = pygame.image.load_sized_svg(str(path), size)
                else:
                    surface = pygame.transform.smoothscale(pygame.image.load(str(path)), size)
        except (FileNotFoundError, pygame.error):
            surface = pygame.Surface(size, pygame.SRCALPHA)
            surface.fill(MISSING_COLOR)
        if pygame.display.get_surface() is not None:
            surface = surface.convert_alpha()
        return surface.copy()
