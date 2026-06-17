"""
Combine server_config, milestone buffs, and guild live events for PvE rewards.
"""

from __future__ import annotations

import json
from typing import Any, Optional, Tuple
from uuid import UUID

from services.live_events.live_event_service import LiveEventService
from services.milestones.milestone_service import MilestoneService


def _parse_world_event_multipliers(state: Any) -> Tuple[float, float]:
    """Read xp/gold multipliers from world_events.state JSONB."""
    if state is None:
        return 1.0, 1.0
    if isinstance(state, str):
        try:
            state = json.loads(state)
        except (json.JSONDecodeError, TypeError):
            return 1.0, 1.0
    if not isinstance(state, dict):
        return 1.0, 1.0
    try:
        xp = float(state.get("xp_multiplier") or 1.0)
        gold = float(state.get("gold_multiplier") or 1.0)
    except (TypeError, ValueError):
        return 1.0, 1.0
    return max(0.0, xp), max(0.0, gold)


async def _active_world_event_multipliers(db) -> Tuple[float, float]:
    row = await db.fetchrow(
        """
        SELECT state FROM world_events
        WHERE is_active=TRUE AND ends_at > NOW()
        ORDER BY started_at DESC
        LIMIT 1
        """
    )
    if not row:
        return 1.0, 1.0
    return _parse_world_event_multipliers(row.get("state"))


async def get_combined_reward_multipliers(
    db,
    guild_id: Optional[int],
    *,
    ingame_guild_id: Optional[UUID] = None,
) -> Tuple[float, float, float]:
    """
    Returns (xp_mult, gold_mult, explore_boss_chance_add).
    explore_boss_chance_add is summed from live events and capped (see LiveEventService).
    When ingame_guild_id is set, guild tech additive bonuses are applied on top (members only).
    """
    xp_mult = 1.0
    gold_mult = 1.0
    boss_add = 0.0
    if guild_id:
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

    if ingame_guild_id:
        try:
            from services.guild.guild_tech import merged_tech_multipliers

            tx, tg, tb = await merged_tech_multipliers(db, ingame_guild_id)
            xp_mult *= 1.0 + tx
            gold_mult *= 1.0 + tg
            boss_add += tb
        except Exception:
            pass

    try:
        wx, wg = await _active_world_event_multipliers(db)
        xp_mult *= wx
        gold_mult *= wg
    except Exception:
        pass

    return xp_mult, gold_mult, boss_add
