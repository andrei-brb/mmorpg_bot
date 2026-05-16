"""Guild hall quest board: daily/weekly hall goals with per-member claim rewards."""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

log = logging.getLogger("guild.quests")

GUILD_QUESTS: Dict[str, Dict[str, Any]] = {
    "daily_hall_muster": {
        "period": "daily",
        "name": "Hall Muster",
        "description": "Members check in at the guild hall today.",
        "metric": "checkin",
        "target": 3,
        "rewards": {"gold": 40, "character_xp": 30, "guild_xp": 15},
    },
    "daily_treasury_tithe": {
        "period": "daily",
        "name": "Treasury Tithe",
        "description": "Donate gold to the guild bank today.",
        "metric": "bank_deposit",
        "target": 2000,
        "rewards": {"gold": 50, "character_xp": 25, "guild_xp": 20},
    },
    "daily_strike_force": {
        "period": "daily",
        "name": "Strike Force",
        "description": "Land raid strikes as a hall.",
        "metric": "raid_strike",
        "target": 15,
        "rewards": {"gold": 35, "character_xp": 40, "guild_xp": 10},
    },
    "weekly_boss_slayer": {
        "period": "weekly",
        "name": "Boss Slayer",
        "description": "Defeat the guild world boss this week.",
        "metric": "boss_defeat",
        "target": 1,
        "rewards": {"gold": 200, "character_xp": 120, "guild_xp": 80},
    },
    "weekly_sortie_complete": {
        "period": "weekly",
        "name": "Sortie Complete",
        "description": "Clear a guild raid this week.",
        "metric": "raid_clear",
        "target": 1,
        "rewards": {"gold": 180, "character_xp": 100, "guild_xp": 100},
    },
    "weekly_dungeon_delvers": {
        "period": "weekly",
        "name": "Dungeon Delvers",
        "description": "Clear dungeon floors as guild members.",
        "metric": "dungeon_floor",
        "target": 10,
        "rewards": {"gold": 150, "character_xp": 90, "guild_xp": 60},
    },
    "weekly_hunt_tally": {
        "period": "weekly",
        "name": "Hunt Tally",
        "description": "Slay foes while in the guild this week.",
        "metric": "combat_kill",
        "target": 40,
        "rewards": {"gold": 120, "character_xp": 80, "guild_xp": 50},
    },
    "weekly_explore_scouts": {
        "period": "weekly",
        "name": "Scout Reports",
        "description": "Complete explore outings this week.",
        "metric": "explore",
        "target": 12,
        "rewards": {"gold": 100, "character_xp": 70, "guild_xp": 40},
    },
}


def utc_today() -> date:
    return datetime.now(timezone.utc).date()


def period_key(quest: Dict[str, Any], on: Optional[date] = None) -> str:
    d = on or utc_today()
    period = quest.get("period") or "daily"
    if period == "weekly":
        iso = d.isocalendar()
        return f"weekly:{iso.year}-W{iso.week:02d}"
    return f"daily:{d.isoformat()}"


def _quests_for_metric(metric: str) -> List[Tuple[str, Dict[str, Any]]]:
    return [(k, v) for k, v in GUILD_QUESTS.items() if v.get("metric") == metric]


async def _get_progress(
    db, guild_id: UUID, quest_key: str, pkey: str
) -> Tuple[int, Optional[datetime]]:
    row = await db.fetchrow(
        """
        SELECT current_value, completed_at FROM guild_quest_progress
        WHERE guild_id = $1 AND quest_key = $2 AND period_key = $3
        """,
        guild_id,
        quest_key,
        pkey,
    )
    if not row:
        return 0, None
    return int(row["current_value"] or 0), row.get("completed_at")


async def record_event(
    db,
    guild_id: UUID,
    metric: str,
    amount: int = 1,
    character_id: Optional[UUID] = None,
) -> None:
    """Increment hall progress for all active quests matching metric."""
    if not guild_id or amount <= 0:
        return
    today = utc_today()
    for quest_key, cfg in _quests_for_metric(metric):
        pkey = period_key(cfg, today)
        target = int(cfg.get("target") or 1)
        current, completed_at = await _get_progress(db, guild_id, quest_key, pkey)
        if completed_at is not None:
            continue
        new_val = current + amount
        if new_val >= target:
            await db.execute(
                """
                INSERT INTO guild_quest_progress (guild_id, quest_key, period_key, current_value, completed_at)
                VALUES ($1, $2, $3, $4, NOW())
                ON CONFLICT (guild_id, quest_key, period_key) DO UPDATE
                SET current_value = $4,
                    completed_at = COALESCE(guild_quest_progress.completed_at, NOW()),
                    updated_at = NOW()
                """,
                guild_id,
                quest_key,
                pkey,
                new_val,
            )
            try:
                from services.guild.guild_feed import post_system

                await post_system(
                    db,
                    guild_id,
                    f"Hall quest complete: **{cfg['name']}** — members may claim rewards.",
                    "system_quest",
                    {"quest_key": quest_key, "period_key": pkey},
                )
            except Exception:
                pass
        else:
            await db.execute(
                """
                INSERT INTO guild_quest_progress (guild_id, quest_key, period_key, current_value)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (guild_id, quest_key, period_key) DO UPDATE
                SET current_value = guild_quest_progress.current_value + $4,
                    updated_at = NOW()
                """,
                guild_id,
                quest_key,
                pkey,
                amount,
            )


async def _claimed(db, guild_id: UUID, quest_key: str, pkey: str, character_id: UUID) -> bool:
    row = await db.fetchrow(
        """
        SELECT 1 FROM guild_quest_claims
        WHERE guild_id = $1 AND quest_key = $2 AND period_key = $3 AND character_id = $4
        """,
        guild_id,
        quest_key,
        pkey,
        character_id,
    )
    return row is not None


async def list_for_guild(
    db, guild_id: UUID, character_id: UUID
) -> Dict[str, List[Dict[str, Any]]]:
    today = utc_today()
    daily: List[Dict[str, Any]] = []
    weekly: List[Dict[str, Any]] = []

    for quest_key, cfg in GUILD_QUESTS.items():
        pkey = period_key(cfg, today)
        target = int(cfg.get("target") or 1)
        current, completed_at = await _get_progress(db, guild_id, quest_key, pkey)
        completed = completed_at is not None or current >= target
        claimed = await _claimed(db, guild_id, quest_key, pkey, character_id)
        row = {
            "key": quest_key,
            "period": cfg["period"],
            "name": cfg["name"],
            "description": cfg["description"],
            "metric": cfg["metric"],
            "target": target,
            "current": min(current, target) if completed else current,
            "completed": completed,
            "my_claimed": claimed,
            "can_claim": completed and not claimed,
            "rewards": dict(cfg.get("rewards") or {}),
            "period_key": pkey,
        }
        if cfg["period"] == "weekly":
            weekly.append(row)
        else:
            daily.append(row)

    return {"daily": daily, "weekly": weekly}


async def claim(
    db,
    char_svc,
    guild_id: UUID,
    character_id: UUID,
    quest_key: str,
) -> Tuple[bool, str, Optional[Dict[str, Any]], Optional[Dict[str, List[Dict[str, Any]]]]]:
    if quest_key not in GUILD_QUESTS:
        return False, "Unknown quest.", None, None
    cfg = GUILD_QUESTS[quest_key]
    pkey = period_key(cfg)
    target = int(cfg.get("target") or 1)
    current, completed_at = await _get_progress(db, guild_id, quest_key, pkey)
    if completed_at is None and current < target:
        return False, "Quest not complete yet.", None, None
    if await _claimed(db, guild_id, quest_key, pkey, character_id):
        return False, "Already claimed this period.", None, None

    rewards = cfg.get("rewards") or {}
    delivery: Dict[str, Any] = {
        "gold": 0,
        "character_xp": 0,
        "guild_xp": 0,
        "items": [],
    }
    gold = int(rewards.get("gold") or 0)
    xp = int(rewards.get("character_xp") or 0)
    gxp = int(rewards.get("guild_xp") or 0)
    if gold > 0:
        await char_svc.add_gold(character_id, gold, "guild_quest")
        delivery["gold"] = gold
    if xp > 0:
        await char_svc.award_xp(character_id, xp, 1.0)
        delivery["character_xp"] = xp
    if gxp > 0:
        await db.execute(
            "UPDATE guilds SET guild_xp = guild_xp + $2 WHERE id = $1",
            guild_id,
            gxp,
        )
        delivery["guild_xp"] = gxp

    await db.execute(
        """
        INSERT INTO guild_quest_claims (guild_id, quest_key, period_key, character_id)
        VALUES ($1, $2, $3, $4)
        """,
        guild_id,
        quest_key,
        pkey,
        character_id,
    )
    quests = await list_for_guild(db, guild_id, character_id)
    return True, "Quest reward claimed.", delivery, quests
