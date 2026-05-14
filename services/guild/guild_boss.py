"""Shared HP guild boss: encounters, hits, settlement."""

from __future__ import annotations

import logging
import random
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Mapping, Optional, Tuple
from uuid import UUID

from services.guild.guild_permissions import can_officer_actions

log = logging.getLogger("guild.boss")

BOSS_TEMPLATES: Dict[str, Dict[str, Any]] = {
    "stone_siege_golem": {
        "name": "Stone Siege Golem",
        "hp_max": 400_000,
        "duration_hours": 168,
        "defeat_gold_pool": 4_000,
        "defeat_guild_xp": 300,
        "expire_gold_pool": 1_200,
        "expire_guild_xp": 80,
        "min_participation_gold": 25,
    },
}

MAX_HITS_PER_CHAR_PER_DAY = 50
HIT_COOLDOWN_S = 6


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_ts(ts: Any) -> datetime:
    if ts is None:
        return utcnow()
    if isinstance(ts, datetime):
        if ts.tzinfo is None:
            return ts.replace(tzinfo=timezone.utc)
        return ts.astimezone(timezone.utc)
    return utcnow()


def template_keys() -> List[str]:
    return list(BOSS_TEMPLATES.keys())


async def get_encounter_row(db, encounter_id: UUID) -> Optional[Dict[str, Any]]:
    row = await db.fetchrow("SELECT * FROM guild_boss_encounters WHERE id=$1", encounter_id)
    return dict(row) if row else None


async def active_encounter_for_guild(db, guild_id: UUID) -> Optional[Dict[str, Any]]:
    row = await db.fetchrow(
        """
        SELECT * FROM guild_boss_encounters
        WHERE guild_id = $1 AND status = 'active'
        ORDER BY opens_at DESC
        LIMIT 1
        """,
        guild_id,
    )
    return dict(row) if row else None


async def refresh_encounter_if_expired(
    db, enc: Dict[str, Any], discord_bot: Any = None
) -> Dict[str, Any]:
    if enc.get("status") != "active":
        return enc
    closes = _normalize_ts(enc.get("closes_at"))
    if closes <= utcnow():
        await settle_encounter(db, UUID(str(enc["id"])), "expired", discord_bot)
        row = await db.fetchrow("SELECT * FROM guild_boss_encounters WHERE id=$1", enc["id"])
        return dict(row) if row else enc
    return enc


async def start_encounter(
    db,
    guild_id: UUID,
    boss_key: str,
    guild_rank: Optional[str],
    discord_bot: Any = None,
) -> tuple[Optional[Dict[str, Any]], str]:
    if not can_officer_actions(guild_rank):
        return None, "Only officers or the guildmaster can summon the guild boss."
    if boss_key not in BOSS_TEMPLATES:
        return None, "Unknown boss."

    cur = await active_encounter_for_guild(db, guild_id)
    if cur:
        cur = await refresh_encounter_if_expired(db, cur, discord_bot)
    if cur and cur.get("status") == "active":
        return None, "A guild boss encounter is already active."

    tpl = BOSS_TEMPLATES[boss_key]
    hp = int(tpl["hp_max"])
    now = utcnow()
    hours = int(tpl.get("duration_hours") or 168)
    closes = now + timedelta(hours=hours)
    row = await db.fetchrow(
        """
        INSERT INTO guild_boss_encounters (guild_id, boss_key, hp_remaining, hp_max, status, opens_at, closes_at)
        VALUES ($1, $2, $3, $4, 'active', $5, $6)
        RETURNING *
        """,
        guild_id,
        boss_key,
        hp,
        hp,
        now,
        closes,
    )
    return (dict(row) if row else None), ""


def _roll_damage(char: Mapping[str, Any]) -> int:
    lvl = int(char.get("level") or 1)
    s = int(char.get("str") or 10) + int(char.get("agi") or 10) + int(char.get("int_") or 10)
    base = lvl * 12 + s * 4
    return max(1, int(base * random.uniform(0.88, 1.12)))


async def _hits_today_count(db, encounter_id: UUID, character_id: UUID) -> int:
    v = await db.fetchval(
        """
        SELECT COUNT(*)::int FROM guild_boss_hits
        WHERE encounter_id = $1 AND character_id = $2
          AND created_at >= date_trunc('day', NOW())
        """,
        encounter_id,
        character_id,
    )
    return int(v or 0)


async def apply_hit(
    db,
    char_svc,
    char: Mapping[str, Any],
    encounter_id: UUID,
    discord_bot: Any = None,
) -> tuple[bool, str, Optional[Dict[str, Any]]]:
    enc = await get_encounter_row(db, encounter_id)
    if not enc or enc.get("status") != "active":
        return False, "No active encounter.", None
    enc = await refresh_encounter_if_expired(db, enc, discord_bot)
    if enc.get("status") != "active":
        return False, "Encounter has ended.", None

    cid = UUID(str(char["id"]))
    gid = char.get("guild_id")
    if not gid or UUID(str(gid)) != UUID(str(enc["guild_id"])):
        return False, "Not a member of this guild.", None

    n = await _hits_today_count(db, encounter_id, cid)
    if n >= MAX_HITS_PER_CHAR_PER_DAY:
        return False, "Daily hit limit reached for this boss.", None

    cd = await char_svc.on_cooldown(cid, "guild_boss_hit")
    if cd:
        return False, f"Wait {int(cd) + 1}s before another strike.", None

    dmg = _roll_damage(char)
    hp_rem = int(enc["hp_remaining"] or 0)
    applied = min(dmg, hp_rem)
    if applied <= 0:
        return False, "Boss is already defeated.", None

    new_hp = hp_rem - applied
    defeated = new_hp <= 0

    await db.execute(
        """
        INSERT INTO guild_boss_hits (encounter_id, character_id, damage, source)
        VALUES ($1, $2, $3, 'simplified_roll')
        """,
        encounter_id,
        cid,
        applied,
    )
    await db.execute(
        "UPDATE guild_boss_encounters SET hp_remaining = $2 WHERE id = $1",
        encounter_id,
        new_hp,
    )
    await char_svc.set_cooldown(cid, "guild_boss_hit", HIT_COOLDOWN_S)

    if defeated:
        await settle_encounter(db, encounter_id, "defeated", discord_bot)
        enc2 = await get_encounter_row(db, encounter_id)
        return True, "Victory! Rewards distributed.", enc2

    enc2 = await get_encounter_row(db, encounter_id)
    return True, f"Hit for {applied} damage.", enc2


def _split_gold(pool: int, totals: Dict[UUID, int], min_g: int) -> Dict[UUID, int]:
    total_dmg = sum(totals.values())
    if total_dmg <= 0 or pool <= 0:
        return {}
    raw: Dict[UUID, int] = {}
    for cid, dmg in totals.items():
        g = int(pool * dmg / total_dmg)
        if dmg > 0 and g < min_g:
            g = min_g
        raw[cid] = max(0, g)
    s = sum(raw.values())
    if s > pool and s > 0:
        factor = pool / s
        raw = {k: max(0, int(v * factor)) for k, v in raw.items()}
    return raw


async def settle_encounter(db, encounter_id: UUID, how: str, discord_bot: Any = None) -> None:
    from services.character.character_service import CharacterService
    from services.guild.guild_feed import post_system

    enc = await db.fetchrow(
        """
        UPDATE guild_boss_encounters
        SET status = $2, settled_at = NOW()
        WHERE id = $1 AND status = 'active'
        RETURNING *
        """,
        encounter_id,
        how,
    )
    if not enc:
        return

    tpl = BOSS_TEMPLATES.get(enc["boss_key"]) or BOSS_TEMPLATES["stone_siege_golem"]
    guild_id = UUID(str(enc["guild_id"]))

    rows = await db.fetch(
        """
        SELECT character_id, SUM(damage)::bigint AS total
        FROM guild_boss_hits
        WHERE encounter_id = $1
        GROUP BY character_id
        """,
        encounter_id,
    )
    totals: Dict[UUID, int] = {UUID(str(r["character_id"])): int(r["total"] or 0) for r in rows}

    if how == "defeated":
        pool = int(tpl["defeat_gold_pool"])
        gxp = int(tpl["defeat_guild_xp"])
    else:
        pool = int(tpl["expire_gold_pool"])
        gxp = int(tpl.get("expire_guild_xp") or 80)

    await db.execute(
        "UPDATE guilds SET guild_xp = guild_xp + $2 WHERE id = $1",
        guild_id,
        gxp,
    )

    min_g = int(tpl.get("min_participation_gold") or 10)
    awards = _split_gold(pool, totals, min_g)
    char_svc = CharacterService(db)
    for char_id, gold in awards.items():
        if gold > 0:
            await char_svc.add_gold(char_id, gold, "guild_boss_reward")

    await post_system(
        db,
        guild_id,
        f"Guild boss **{tpl['name']}** ended ({how}). "
        f"Guild earned **{gxp}** guild XP. **{sum(awards.values())}** gold split among contributors.",
        "system_boss",
        {"encounter_id": str(encounter_id), "how": how},
    )

    if discord_bot is not None:
        try:
            import discord

            from services.guild.guild_discord_announce import post_to_guild_announce_channel

            total_gold = sum(awards.values())
            color = 0x27AE60 if how == "defeated" else 0x95A5A6
            emb = discord.Embed(
                title="Guild boss encounter ended",
                description=f"**{tpl['name']}** — _{how}_",
                color=color,
            )
            emb.add_field(name="Guild XP", value=f"+{gxp:,}", inline=True)
            emb.add_field(name="Gold distributed", value=f"{total_gold:,}", inline=True)
            await post_to_guild_announce_channel(discord_bot, db, guild_id, embed=emb)
        except Exception as e:
            log.warning("Discord announce after boss settle: %s", e)


async def leaderboard(db, encounter_id: UUID, limit: int = 15) -> List[Dict[str, Any]]:
    rows = await db.fetch(
        """
        SELECT h.character_id, SUM(h.damage)::bigint AS total_damage, c.name
        FROM guild_boss_hits h
        JOIN characters c ON c.id = h.character_id
        WHERE h.encounter_id = $1
        GROUP BY h.character_id, c.name
        ORDER BY total_damage DESC
        LIMIT $2
        """,
        encounter_id,
        limit,
    )
    return [dict(r) for r in rows]
