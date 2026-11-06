"""UI: everything that touches pygame.

Modules:

- ``assets``: ``SpriteCache`` loads the placeholder SVG sprites at a given
  size, optionally tinted with a player colour.
- ``render``: ``Camera`` (world cells <-> screen pixels, pan, zoom) and
  ``Renderer`` (tiles, buildings, units, HUD).
- ``input``: ``InputController`` turns mouse and keyboard events into
  selection, ``Game`` commands and camera movement.
"""
