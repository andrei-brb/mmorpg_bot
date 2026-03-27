"""
Combine server_config, milestone buffs, and guild live events for PvE rewards.
"""

from __future__ import annotations

from typing import Optional, Tuple

from services.live_events.live_event_service import LiveEventService
from services.milestones.milestone_service import MilestoneService


async def get_combined_reward_multipliers(
    db, guild_id: Optional[int]
) -> Tuple[float, float, float]:
    """
    Returns (xp_mult, gold_mult, explore_boss_chance_add).
    explore_boss_chance_add is summed from live events and capped (see LiveEventService).
    """
    xp_mult = 1.0
    gold_mult = 1.0
    boss_add = 0.0
    if not guild_id:
        return xp_mult, gold_mult, boss_add

    row = await db.fetchrow(
        "SELECT xp_multiplier, gold_multiplier FROM server_config WHERE server_id=$1",
        guild_id,
    )
    if row:
        xp_mult *= float(row["xp_multiplier"] or 1.0)
        gold_mult *= float(row["gold_multiplier"] or 1.0)

    try:
        ms = MilestoneService(db)
        b = await ms.get_active_multipliers(guild_id)
        xp_mult *= float(b["xp_multiplier"])
        gold_mult *= float(b["gold_multiplier"])
    except Exception:
        pass

    try:
        le = LiveEventService(db)
        b = await le.get_reward_multipliers(guild_id)
        xp_mult *= float(b.get("xp_multiplier") or 1.0)
        gold_mult *= float(b.get("gold_multiplier") or 1.0)
        boss_add = float(b.get("explore_boss_chance_add") or 0.0)
    except Exception:
        pass

    return xp_mult, gold_mult, boss_add
