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
    focus: str = "wander",
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

    # Expedition focus reshapes the bands. The base numbers below are the
    # historical ones and remain exactly what "wander" produces, so an
    # unfocused explore is bit-for-bit the roll this has always been.
    from services.exploration.expeditions import apply_to_bands

    shares = apply_to_bands(focus, enemy=0.40, boss=0.15 + add, loot=0.20 + add)

    boss_band_active = bool(zone_patrol_boss_alive) or bool(world_boss_key)
    boss_lo = shares["enemy"]
    boss_hi = boss_lo + shares["boss"]
    loot_hi = boss_hi + shares["loot"]

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
        if r < loot_hi:
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
    if r < loot_hi:
        return {"type": "loot"}
    return {"type": "safe"}
