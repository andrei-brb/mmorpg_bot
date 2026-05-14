"""Guild raid runs: signup, start, complete (MVP instanced rewards)."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from services.guild.guild_permissions import can_officer_actions

log = logging.getLogger("guild.raid")

RAID_TEMPLATES: Dict[str, Dict[str, Any]] = {
    "gnoll_warren_raid": {
        "name": "Gnoll Warren Sortie",
        "min_signups": 1,
        "max_participants": 8,
        "completion_gold_per_player": 150,
        "guild_xp_reward": 120,
    },
}


def raid_keys() -> List[str]:
    return list(RAID_TEMPLATES.keys())


async def create_run(
    db,
    guild_id: UUID,
    template_key: str,
    leader_character_id: UUID,
    guild_rank: Optional[str],
) -> tuple[Optional[Dict[str, Any]], str]:
    if not can_officer_actions(guild_rank):
        return None, "Only officers or the guildmaster can schedule a guild raid."
    if template_key not in RAID_TEMPLATES:
        return None, "Unknown raid."
    tpl = RAID_TEMPLATES[template_key]
    row = await db.fetchrow(
        """
        INSERT INTO guild_raid_runs (guild_id, template_key, status, leader_character_id)
        VALUES ($1, $2, 'recruiting', $3)
        RETURNING *
        """,
        guild_id,
        template_key,
        leader_character_id,
    )
    rid = row["id"]
    await db.execute(
        """
        INSERT INTO guild_raid_participants (run_id, character_id, role)
        VALUES ($1, $2, 'leader')
        ON CONFLICT (run_id, character_id) DO NOTHING
        """,
        rid,
        leader_character_id,
    )
    return dict(row) if row else None, ""


async def signup(db, run_id: UUID, character_id: UUID, guild_id: UUID) -> tuple[bool, str]:
    run = await db.fetchrow("SELECT * FROM guild_raid_runs WHERE id=$1", run_id)
    if not run or run["status"] != "recruiting":
        return False, "Raid is not open for signup."
    if UUID(str(run["guild_id"])) != guild_id:
        return False, "Wrong guild."
    tpl = RAID_TEMPLATES.get(run["template_key"])
    if not tpl:
        return False, "Invalid raid template."
    cnt = await db.fetchval(
        "SELECT COUNT(*)::int FROM guild_raid_participants WHERE run_id=$1",
        run_id,
    )
    if int(cnt or 0) >= int(tpl["max_participants"]):
        return False, "Raid party is full."
    await db.execute(
        """
        INSERT INTO guild_raid_participants (run_id, character_id, role)
        VALUES ($1, $2, 'member')
        ON CONFLICT (run_id, character_id) DO NOTHING
        """,
        run_id,
        character_id,
    )
    return True, ""


async def start_run(
    db,
    run_id: UUID,
    character_id: UUID,
    guild_rank: Optional[str],
) -> tuple[bool, str]:
    if not can_officer_actions(guild_rank):
        return False, "Only officers or the guildmaster can start the raid."
    run = await db.fetchrow("SELECT * FROM guild_raid_runs WHERE id=$1", run_id)
    if not run or run["status"] != "recruiting":
        return False, "Raid cannot be started."
    tpl = RAID_TEMPLATES.get(run["template_key"])
    if not tpl:
        return False, "Invalid template."
    n = await db.fetchval(
        "SELECT COUNT(*)::int FROM guild_raid_participants WHERE run_id=$1",
        run_id,
    )
    if int(n or 0) < int(tpl["min_signups"]):
        return False, "Not enough members signed up."
    await db.execute(
        """
        UPDATE guild_raid_runs
        SET status = 'active', started_at = NOW()
        WHERE id = $1 AND status = 'recruiting'
        """,
        run_id,
    )
    return True, ""


async def complete_run(
    db,
    char_svc,
    run_id: UUID,
    _actor_character_id: UUID,
    guild_rank: Optional[str],
    discord_bot: Any = None,
) -> tuple[bool, str]:
    if not can_officer_actions(guild_rank):
        return False, "Only officers or the guildmaster can complete the raid."
    run = await db.fetchrow("SELECT * FROM guild_raid_runs WHERE id=$1", run_id)
    if not run or run["status"] != "active":
        return False, "Raid is not active."
    tpl = RAID_TEMPLATES.get(run["template_key"])
    if not tpl:
        return False, "Invalid template."
    guild_id = UUID(str(run["guild_id"]))
    gxp = int(tpl.get("guild_xp_reward") or 0)
    gold_each = int(tpl.get("completion_gold_per_player") or 0)

    parts = await db.fetch(
        "SELECT character_id FROM guild_raid_participants WHERE run_id=$1",
        run_id,
    )
    for p in parts:
        cid = UUID(str(p["character_id"]))
        if gold_each > 0:
            await char_svc.add_gold(cid, gold_each, "guild_raid_reward")

    await db.execute(
        """
        UPDATE guild_raid_runs
        SET status = 'completed', completed_at = NOW()
        WHERE id = $1 AND status = 'active'
        """,
        run_id,
    )
    if gxp > 0:
        await db.execute(
            "UPDATE guilds SET guild_xp = guild_xp + $2 WHERE id = $1",
            guild_id,
            gxp,
        )

    from services.guild.guild_feed import post_system

    await post_system(
        db,
        guild_id,
        f"Guild raid **{tpl['name']}** completed! Each participant earned **{gold_each}** gold.",
        "system_raid",
        {"run_id": str(run_id), "template": run["template_key"]},
    )

    if discord_bot is not None:
        try:
            import discord

            from services.guild.guild_discord_announce import post_to_guild_announce_channel

            n = len(parts)
            emb = discord.Embed(
                title="Guild raid completed",
                description=f"**{tpl['name']}**",
                color=0x9B59B6,
            )
            emb.add_field(name="Participants", value=str(n), inline=True)
            emb.add_field(name="Gold each", value=f"{gold_each:,}", inline=True)
            if gxp:
                emb.add_field(name="Guild XP", value=f"+{gxp:,}", inline=True)
            await post_to_guild_announce_channel(discord_bot, db, guild_id, embed=emb)
        except Exception as e:
            log.warning("Discord announce after raid complete: %s", e)

    return True, ""


async def list_runs(db, guild_id: UUID, limit: int = 10) -> List[Dict[str, Any]]:
    rows = await db.fetch(
        """
        SELECT r.*, u.username AS leader_name
        FROM guild_raid_runs r
        JOIN characters c ON c.id = r.leader_character_id
        JOIN players u ON u.id = c.player_id
        WHERE r.guild_id = $1
        ORDER BY r.created_at DESC
        LIMIT $2
        """,
        guild_id,
        limit,
    )
    return [dict(x) for x in rows]


async def participants_for_run(db, run_id: UUID) -> List[Dict[str, Any]]:
    rows = await db.fetch(
        """
        SELECT p.character_id, p.role, c.name
        FROM guild_raid_participants p
        JOIN characters c ON c.id = p.character_id
        WHERE p.run_id = $1
        ORDER BY p.role DESC, c.name
        """,
        run_id,
    )
    return [dict(x) for x in rows]
