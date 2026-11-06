"""UI: everything that touches pygame.

Modules:

- ``assets``: ``SpriteCache`` loads the placeholder SVG sprites at a given
  size, optionally tinted with a player colour.
- ``render``: ``Camera`` (world cells <-> screen pixels, pan, zoom) and
  ``Renderer`` (tiles, buildings, units, top HUD, and the panel).
- ``panel``: ``Panel``, the SC2-style lower panel: selection info, the
  selected building's queue, and command buttons with hotkeys.
- ``input``: ``InputController`` turns mouse and keyboard events into
  selection, targeting mode, ``Game`` commands and camera movement.
"""
