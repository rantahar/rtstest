"""Players: identity, colour and resource stock.

A player's id is its index in ``Game.players``. The environmental hazard is
not a player; its units are owned by ``HAZARD_OWNER``.
"""

from dataclasses import dataclass

__all__ = ["Player", "make_players", "HAZARD_OWNER", "STARTING_RESOURCES"]

HAZARD_OWNER = -1
STARTING_RESOURCES = 150
PLAYER_COLORS = [(70, 130, 240), (240, 200, 60), (80, 200, 100),
                 (180, 100, 230), (60, 210, 210), (240, 140, 50)]


@dataclass
class Player:
    """One participant: human or computer controlled."""

    id: int
    name: str
    color: tuple[int, int, int]
    is_ai: bool = False
    resources: int = STARTING_RESOURCES
    alive: bool = True


def make_players(n: int, human_player: int | None = 0) -> list[Player]:
    """Create ``n`` players; all but ``human_player`` are computer controlled."""
    return [Player(i, "You" if i == human_player else f"AI {i}",
                   PLAYER_COLORS[i % len(PLAYER_COLORS)], is_ai=i != human_player)
            for i in range(n)]
