"""UI: everything that touches pygame.

Public API (import from ``rtstest.ui``):

- ``Camera``: world cells <-> screen pixels, pan, zoom; ``insets`` keep map
  edges scrollable from under the HUD and panel.
- ``Renderer``: draws a frame (tiles, buildings, units, placement ghost,
  top HUD, lower panel); owns the ``Panel`` as ``renderer.panel``.
- ``InputController``: selection, targeting/placing modes, build menu,
  ``Game`` commands and camera movement from pygame events.
- ``HUD_HEIGHT``, ``PANEL_HEIGHT``: pixel heights of the top bar and panel.

Modules: ``render``, ``camera``, ``input``, ``panel`` (SC2-style command panel),
``assets`` (SVG sprite cache).
"""

from rtstest.ui.camera import Camera
from rtstest.ui.input import InputController
from rtstest.ui.panel import PANEL_HEIGHT
from rtstest.ui.render import HUD_HEIGHT, Renderer

__all__ = ["Camera", "Renderer", "InputController", "HUD_HEIGHT", "PANEL_HEIGHT"]
