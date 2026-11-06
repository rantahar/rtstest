"""Pushback between overlapping units: they may pass through each other but drift apart.

Units are bucketed by cell each tick and each unit is compared only with
units in the 3x3 cells around it. Rules:

- A unit standing on its reserved cell with no path (working, attacking,
  or arrived) is anchored and never pushed.
- A moving unit overlapping a stopped one is pushed sideways relative to its
  heading, so it slides between stopped units instead of stopping.
- A stopped unit is not pushed by moving units.
- Two moving units push each other gently; two stopped units push fully.
- A push never moves a unit onto an impassable cell.
"""

from __future__ import annotations

import math
from collections import defaultdict
from typing import TYPE_CHECKING

from rtstest.world import Cell, Grid

if TYPE_CHECKING:
    from rtstest.sim.units import Unit

__all__ = ["apply_pushback"]

PUSH_RADIUS = 0.7
PUSH_SPEED = 2.0
MOVING_PAIR_FACTOR = 0.3
GOLDEN_ANGLE = 2.399963


def _is_anchored(unit: Unit) -> bool:
    """Whether the unit stands still on its own reserved cell."""
    return not unit.path and unit.reserved == unit.cell


def apply_pushback(units: list[Unit], grid: Grid, dt: float) -> None:
    """Separate overlapping units by one tick's worth of pushing."""
    buckets: dict[Cell, list[Unit]] = defaultdict(list)
    for u in units:
        buckets[u.cell].append(u)
    pushes = []
    for u in units:
        if _is_anchored(u):
            continue
        push = _push_on(u, buckets)
        if push is not None:
            pushes.append((u, push))
    for u, (px, py) in pushes:
        _shift(u, grid, px * PUSH_SPEED * dt, py * PUSH_SPEED * dt)


def _push_on(u: Unit, buckets: dict[Cell, list[Unit]]) -> tuple[float, float] | None:
    """Sum of pushes on ``u`` from overlapping neighbours, or None."""
    moving = bool(u.path)
    cx, cy = u.cell
    px = py = 0.0
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            for o in buckets.get((cx + dx, cy + dy), ()):
                if o is u:
                    continue
                other_moving = bool(o.path)
                if other_moving and not moving:
                    continue
                ox, oy = u.x - o.x, u.y - o.y
                d = math.hypot(ox, oy)
                if d >= PUSH_RADIUS:
                    continue
                if d < 1e-6:
                    angle = u.id * GOLDEN_ANGLE
                    ox, oy, d = math.cos(angle), math.sin(angle), 1.0
                ox, oy = ox / d, oy / d
                strength = (PUSH_RADIUS - d) / PUSH_RADIUS
                if moving and other_moving:
                    strength *= MOVING_PAIR_FACTOR
                elif moving:
                    ox, oy = _sideways(u, ox, oy)
                px += ox * strength
                py += oy * strength
    if px == 0.0 and py == 0.0:
        return None
    return px, py


def _sideways(u: Unit, ox: float, oy: float) -> tuple[float, float]:
    """Component of push direction (ox, oy) perpendicular to u's heading, unit length."""
    hx, hy = u.path[0][0] + 0.5 - u.x, u.path[0][1] + 0.5 - u.y
    h = math.hypot(hx, hy)
    if h < 1e-6:
        return ox, oy
    hx, hy = hx / h, hy / h
    along = ox * hx + oy * hy
    sx, sy = ox - along * hx, oy - along * hy
    s = math.hypot(sx, sy)
    if s < 0.1:
        sign = 1 if u.id % 2 else -1
        return -hy * sign, hx * sign
    return sx / s, sy / s


def _shift(u: Unit, grid: Grid, dx: float, dy: float) -> None:
    """Move a unit by (dx, dy), per axis, only onto passable cells."""
    nx = u.x + dx
    if grid.is_passable((math.floor(nx), math.floor(u.y))):
        u.x = nx
    ny = u.y + dy
    if grid.is_passable((math.floor(u.x), math.floor(ny))):
        u.y = ny
