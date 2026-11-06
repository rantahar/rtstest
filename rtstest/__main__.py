"""Entry point: open a window and run the game loop.

The simulation advances in fixed ``TICK`` steps independent of the frame
rate; input and rendering run once per frame.
"""

import argparse

import pygame

from rtstest.sim import TICK, Game
from rtstest.ui import HUD_HEIGHT, PANEL_HEIGHT, Camera, InputController, Renderer

__all__ = ["main"]

WINDOW_SIZE = (1280, 800)
FPS = 60
MAX_FRAME_TIME = 0.25
HUMAN_PLAYER = 0


def main(argv: list[str] | None = None) -> int:
    """Parse arguments and run the game until the window closes."""
    parser = argparse.ArgumentParser(prog="rtstest", description=__doc__)
    parser.add_argument("--seed", type=int, default=0, help="map and hazard seed")
    parser.add_argument("--players", type=int, default=3, help="number of players")
    parser.add_argument("--size", type=int, default=64, help="map width and height in cells")
    parser.add_argument("--frames", type=int, default=0,
                        help="quit after this many frames (0 = run until closed)")
    args = parser.parse_args(argv)

    pygame.init()
    screen = pygame.display.set_mode(WINDOW_SIZE, pygame.RESIZABLE)
    pygame.display.set_caption("rtstest")
    clock = pygame.time.Clock()

    game = Game(args.size, args.size, args.players, args.seed, HUMAN_PLAYER)
    camera = Camera(screen.get_size(), insets=(HUD_HEIGHT, PANEL_HEIGHT))
    home = game.buildings_of(HUMAN_PLAYER)[0]
    camera.center_on(*home.center)
    renderer = Renderer(screen)
    controller = InputController(game, camera, renderer.panel, HUMAN_PLAYER)

    accumulator = 0.0
    frames = 0
    running = True
    while running:
        dt = min(clock.tick(FPS) / 1000, MAX_FRAME_TIME)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                running = controller.cancel_targeting()
            elif event.type == pygame.VIDEORESIZE:
                camera.resize(event.size)
            else:
                controller.handle_event(event)
        controller.update(dt)
        accumulator += dt
        while accumulator >= TICK:
            game.step()
            accumulator -= TICK
        renderer.draw(game, camera, HUMAN_PLAYER, controller.selection, controller.drag_rect(),
                      controller.targeting, controller.menu, controller.ghost())
        pygame.display.flip()
        frames += 1
        if args.frames and frames >= args.frames:
            running = False
    pygame.quit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
