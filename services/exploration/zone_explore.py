"""Shared explore / encounter roll (Discord + Activity)."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, Any, Dict

from config.settings import ENEMIES

if TYPE_CHECKING:
    pass


def roll_explore_outcome(zone: Any, boss_chance_add: float = 0.0) -> Dict[str, Any]:
    """
    Roll loot / safe / enemy / boss. boss_chance_add expands the boss band,
    taken from the safe band (see inline comments).
    """
    add = min(max(float(boss_chance_add), 0.0), 0.15)
    r = random.random()
    # enemy [0, 0.40)
    if r < 0.40:
        key = random.choice(zone.enemies)
        e = ENEMIES.get(key)
        return {
            "type": "enemy",
            "key": key,
            "name": e.name if e else key.replace("_", " ").title(),
            "emoji": e.emoji if e else "👾",
        }
    # boss [0.40, 0.55 + add)
    if r < 0.55 + add:
        key = random.choice(zone.bosses) if zone.bosses else random.choice(zone.enemies)
        e = ENEMIES.get(key)
        return {
            "type": "boss",
            "key": key,
            "name": e.name if e else key.replace("_", " ").title(),
            "emoji": e.emoji if e else "💀",
        }
    # loot [0.55 + add, 0.75 + add)
    if r < 0.75 + add:
        return {"type": "loot"}
    return {"type": "safe"}
