"""Shared explore / encounter roll (Discord + Activity)."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, Any, Dict, Optional

from config.settings import ENEMIES

if TYPE_CHECKING:
    pass


def roll_explore_outcome(
    zone: Any,
    boss_chance_add: float = 0.0,
    *,
    zone_patrol_boss_alive: bool = True,
    world_boss_key: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Roll loot / safe / enemy / boss. boss_chance_add expands the boss band (capped),
    taken from the safe band.

    If zone_patrol_boss_alive is False, the normal patrol boss band is merged into
    the enemy band — unless world_boss_key is set (lore window), in which case the
    boss band still targets that key only.
    """
    add = min(max(float(boss_chance_add), 0.0), 0.15)
    r = random.random()

    boss_band_active = bool(zone_patrol_boss_alive) or bool(world_boss_key)
    boss_lo = 0.40
    boss_hi = 0.55 + add

    if boss_band_active:
        if r < boss_lo:
            key = random.choice(zone.enemies)
            e = ENEMIES.get(key)
            return {
                "type": "enemy",
                "key": key,
                "name": e.name if e else key.replace("_", " ").title(),
                "emoji": e.emoji if e else "👾",
            }
        if r < boss_hi:
            if world_boss_key and ENEMIES.get(world_boss_key):
                key = world_boss_key
            else:
                key = random.choice(zone.bosses) if zone.bosses else random.choice(zone.enemies)
            e = ENEMIES.get(key)
            return {
                "type": "boss",
                "key": key,
                "name": e.name if e else key.replace("_", " ").title(),
                "emoji": e.emoji if e else "💀",
            }
        if r < 0.75 + add:
            return {"type": "loot"}
        return {"type": "safe"}

    # Patrol dead and no lore window: boss probability becomes extra enemy encounters.
    if r < boss_hi:
        key = random.choice(zone.enemies)
        e = ENEMIES.get(key)
        return {
            "type": "enemy",
            "key": key,
            "name": e.name if e else key.replace("_", " ").title(),
            "emoji": e.emoji if e else "👾",
        }
    if r < 0.75 + add:
        return {"type": "loot"}
    return {"type": "safe"}
