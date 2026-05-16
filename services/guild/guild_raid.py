"""Guild raid runs: signup, shared HP strikes, auto-settle, per-member bonus combat."""

from __future__ import annotations

import logging
import random
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from services.guild.guild_permissions import can_officer_actions

log = logging.getLogger("guild.raid")

BONUS_CLAIM_GRACE_HOURS = 48
STRIKE_COOLDOWN_S = 8
MAX_STRIKES_PER_CHAR_PER_DAY = 80

RAID_TEMPLATES: Dict[str, Dict[str, Any]] = {
    "gnoll_warren_raid": {
        "name": "Gnoll Warren Sortie",
        "min_signups": 1,
        "max_participants": 8,
        "hp_max": 25_000,
        "base_gold_per_player": 150,
        "guild_xp_reward": 120,
        "bonus_gold": 75,
        "bonus_xp": 40,
        "bonus_enemy_key": "gnoll_raider",
        "requires_tech": None,
        "strike_damage_mult": 1.0,
    },
    "ironfang_hold_raid": {
        "name": "Ironfang Hold Assault",
        "min_signups": 1,
        "max_participants": 8,
        "hp_max": 45_000,
        "base_gold_per_player": 220,
        "guild_xp_reward": 200,
        "bonus_gold": 120,
        "bonus_xp": 65,
        "bonus_enemy_key": "defias_bandit",
        "requires_tech": "guild_war_raid_2",
        "strike_damage_mult": 1.0,
    },
    "shadow_crypt_raid": {
        "name": "Shadow Crypt Expedition",
        "min_signups": 1,
        "max_participants": 8,
        "hp_max": 70_000,
        "base_gold_per_player": 320,
        "guild_xp_reward": 350,
        "bonus_gold": 180,
        "bonus_xp": 90,
        "bonus_enemy_key": "skeleton",
        "requires_tech": "guild_war_raid_3",
        "strike_damage_mult": 1.0,
    },
}


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def raid_keys() -> List[str]:
    return list(RAID_TEMPLATES.keys())


async def unlocked_raid_templates(db, guild_id: UUID) -> List[str]:
    from services.guild import guild_tech as guild_tech_mod

    unlocked = set(await guild_tech_mod.fetch_unlocked_ids(db, guild_id))
    out: List[str] = []
    for key, tpl in RAID_TEMPLATES.items():
        req = tpl.get("requires_tech")
        if req and req not in unlocked:
            continue
        out.append(key)
    return out


async def _is_signed_up(db, run_id: UUID, character_id: UUID) -> bool:
    row = await db.fetchrow(
        "SELECT 1 FROM guild_raid_participants WHERE run_id=$1 AND character_id=$2",
        run_id,
        character_id,
    )
    return row is not None


async def _strike_damage(db, guild_id: UUID, char: Any, tpl: Dict[str, Any]) -> int:
    from services.guild.guild_boss import _roll_damage
    from services.guild import guild_tech as guild_tech_mod

    base = _roll_damage(char)
    tech_mult = await guild_tech_mod.strike_damage_mult(db, guild_id)
    mult = float(tpl.get("strike_damage_mult") or 1.0) * tech_mult
    return max(1, int(base * mult))


async def _strikes_today(db, run_id: UUID, character_id: UUID) -> int:
    v = await db.fetchval(
        """
        SELECT COUNT(*)::int FROM guild_raid_strikes
        WHERE run_id = $1 AND character_id = $2
          AND created_at >= date_trunc('day', NOW())
        """,
        run_id,
        character_id,
    )
    return int(v or 0)


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
    available = await unlocked_raid_templates(db, guild_id)
    if template_key not in available:
        return None, "Your guild has not unlocked this raid tier (Guild Tech → War branch)."

    active = await db.fetchrow(
        """
        SELECT id FROM guild_raid_runs
        WHERE guild_id = $1 AND status IN ('recruiting', 'active')
        LIMIT 1
        """,
        guild_id,
    )
    if active:
        return None, "A raid is already recruiting or in progress."

    tpl = RAID_TEMPLATES[template_key]
    recruit_ends = utcnow() + timedelta(hours=24)
    row = await db.fetchrow(
        """
        INSERT INTO guild_raid_runs (
            guild_id, template_key, status, leader_character_id, recruit_ends_at
        )
        VALUES ($1, $2, 'recruiting', $3, $4)
        RETURNING *
        """,
        guild_id,
        template_key,
        leader_character_id,
        recruit_ends,
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
    hp = int(tpl["hp_max"])
    await db.execute(
        """
        UPDATE guild_raid_runs
        SET status = 'active',
            started_at = NOW(),
            boss_hp_remaining = $2,
            boss_hp_max = $2
        WHERE id = $1 AND status = 'recruiting'
        """,
        run_id,
        hp,
    )
    return True, ""


async def cancel_run(
    db,
    run_id: UUID,
    guild_rank: Optional[str],
) -> tuple[bool, str]:
    if not can_officer_actions(guild_rank):
        return False, "Only officers or the guildmaster can cancel the raid."
    run = await db.fetchrow("SELECT * FROM guild_raid_runs WHERE id=$1", run_id)
    if not run or run["status"] not in ("recruiting", "active"):
        return False, "Raid cannot be cancelled."
    await db.execute(
        """
        UPDATE guild_raid_runs SET status = 'cancelled', completed_at = NOW()
        WHERE id = $1
        """,
        run_id,
    )
    return True, ""


async def _participant_count(db, run_id: UUID) -> int:
    v = await db.fetchval(
        "SELECT COUNT(*)::int FROM guild_raid_participants WHERE run_id=$1",
        run_id,
    )
    return int(v or 0)


async def settle_run(
    db,
    char_svc,
    run_id: UUID,
    discord_bot: Any = None,
) -> tuple[bool, str]:
    run = await db.fetchrow("SELECT * FROM guild_raid_runs WHERE id=$1", run_id)
    if not run or run["status"] != "active":
        return False, "Raid is not active."
    if int(run["boss_hp_remaining"] or 0) > 0:
        return False, "Raid target still standing."

    tpl = RAID_TEMPLATES.get(run["template_key"])
    if not tpl:
        return False, "Invalid template."
    guild_id = UUID(str(run["guild_id"]))
    n = await _participant_count(db, run_id)
    scale = 1.0 + 0.05 * max(0, n - 1)
    gold_each = max(1, int(int(tpl["base_gold_per_player"]) * scale))
    gxp = int(tpl.get("guild_xp_reward") or 0)

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
        f"Guild raid **{tpl['name']}** cleared! Each participant earned **{gold_each:,}** gold.",
        "system_raid",
        {"run_id": str(run_id), "template": run["template_key"]},
    )

    if discord_bot is not None:
        try:
            import discord

            from services.guild.guild_discord_announce import post_to_guild_announce_channel

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


async def strike(
    db,
    char_svc,
    run_id: UUID,
    char: Dict[str, Any],
    discord_bot: Any = None,
) -> tuple[bool, str, Optional[Dict[str, Any]]]:
    run = await db.fetchrow("SELECT * FROM guild_raid_runs WHERE id=$1", run_id)
    if not run or run["status"] != "active":
        return False, "Raid is not active.", None
    cid = UUID(str(char["id"]))
    gid = char.get("guild_id")
    if not gid or UUID(str(gid)) != UUID(str(run["guild_id"])):
        return False, "Not a member of this guild.", None
    if not await _is_signed_up(db, run_id, cid):
        return False, "Sign up for this raid first.", None

    tpl = RAID_TEMPLATES.get(run["template_key"])
    if not tpl:
        return False, "Invalid template.", None

    n_today = await _strikes_today(db, run_id, cid)
    if n_today >= MAX_STRIKES_PER_CHAR_PER_DAY:
        return False, "Daily strike limit reached for this raid.", None

    cd = await char_svc.on_cooldown(cid, "guild_raid_strike")
    if cd:
        return False, f"Wait {int(cd) + 1}s before another strike.", None

    hp_rem = int(run["boss_hp_remaining"] or 0)
    if hp_rem <= 0:
        return False, "Raid target already destroyed.", None

    gid = UUID(str(run["guild_id"]))
    dmg = await _strike_damage(db, gid, char, tpl)
    applied = min(dmg, hp_rem)
    new_hp = hp_rem - applied

    await db.execute(
        """
        INSERT INTO guild_raid_strikes (run_id, character_id, damage)
        VALUES ($1, $2, $3)
        """,
        run_id,
        cid,
        applied,
    )
    await db.execute(
        "UPDATE guild_raid_runs SET boss_hp_remaining = $2 WHERE id = $1",
        run_id,
        new_hp,
    )
    await char_svc.set_cooldown(cid, "guild_raid_strike", STRIKE_COOLDOWN_S)

    defeated = new_hp <= 0
    if defeated:
        await settle_run(db, char_svc, run_id, discord_bot)

    run2 = await db.fetchrow("SELECT * FROM guild_raid_runs WHERE id=$1", run_id)
    return True, f"Strike for {applied:,} damage." + (" Raid cleared!" if defeated else ""), dict(run2) if run2 else None


async def _bonus_claim_allowed(run: Dict[str, Any]) -> bool:
    st = run.get("status")
    if st == "active":
        return True
    if st == "completed":
        completed_at = run.get("completed_at")
        if completed_at is None:
            return True
        if isinstance(completed_at, datetime):
            if completed_at.tzinfo is None:
                completed_at = completed_at.replace(tzinfo=timezone.utc)
            return completed_at + timedelta(hours=BONUS_CLAIM_GRACE_HOURS) > utcnow()
    return False


async def has_bonus_claimed(db, run_id: UUID, character_id: UUID) -> bool:
    row = await db.fetchrow(
        "SELECT 1 FROM guild_raid_bonus_claims WHERE run_id=$1 AND character_id=$2",
        run_id,
        character_id,
    )
    return row is not None


async def start_bonus_combat(
    db,
    run_id: UUID,
    character_id: UUID,
    guild_id: UUID,
) -> tuple[bool, str, Optional[Dict[str, Any]]]:
    """Return enemy_key for Activity combat; caller starts fight."""
    run = await db.fetchrow("SELECT * FROM guild_raid_runs WHERE id=$1", run_id)
    if not run:
        return False, "Raid not found.", None
    if UUID(str(run["guild_id"])) != guild_id:
        return False, "Wrong guild.", None
    if not await _bonus_claim_allowed(run):
        return False, "Bonus encounter is not available for this raid.", None
    if not await _is_signed_up(db, run_id, character_id):
        return False, "Sign up for this raid first.", None
    if await has_bonus_claimed(db, run_id, character_id):
        return False, "You already claimed the raid bonus reward.", None

    tpl = RAID_TEMPLATES.get(run["template_key"])
    if not tpl:
        return False, "Invalid template.", None
    enemy_key = str(tpl.get("bonus_enemy_key") or "gnoll_raider")
    return True, "", {
        "enemy_key": enemy_key,
        "run_id": str(run_id),
        "template_name": tpl.get("name"),
    }


async def grant_bonus_claim(
    db,
    char_svc,
    run_id: UUID,
    character_id: UUID,
) -> tuple[bool, str, Optional[Dict[str, Any]]]:
    run = await db.fetchrow("SELECT * FROM guild_raid_runs WHERE id=$1", run_id)
    if not run:
        return False, "Raid not found.", None
    if not await _bonus_claim_allowed(run):
        return False, "Bonus claim window closed.", None
    if not await _is_signed_up(db, run_id, character_id):
        return False, "You were not part of this raid.", None
    if await has_bonus_claimed(db, run_id, character_id):
        return False, "Bonus already claimed.", None

    tpl = RAID_TEMPLATES.get(run["template_key"])
    if not tpl:
        return False, "Invalid template.", None

    bonus_gold = int(tpl.get("bonus_gold") or 0)
    bonus_xp = int(tpl.get("bonus_xp") or 0)

    await db.execute(
        """
        INSERT INTO guild_raid_bonus_claims (run_id, character_id)
        VALUES ($1, $2)
        """,
        run_id,
        character_id,
    )
    xp_result = None
    if bonus_gold > 0:
        await char_svc.add_gold(character_id, bonus_gold, "guild_raid_bonus")
    if bonus_xp > 0:
        xp_result = await char_svc.award_xp(character_id, bonus_xp, 1.0)

    return True, "Raid bonus claimed.", {
        "bonus_gold": bonus_gold,
        "bonus_xp": bonus_xp,
        "xp_result": xp_result,
    }


async def strike_leaderboard(db, run_id: UUID) -> List[Dict[str, Any]]:
    rows = await db.fetch(
        """
        SELECT c.name, SUM(s.damage)::bigint AS total_damage, COUNT(*)::int AS strikes
        FROM guild_raid_strikes s
        JOIN characters c ON c.id = s.character_id
        WHERE s.run_id = $1
        GROUP BY c.id, c.name
        ORDER BY total_damage DESC
        LIMIT 20
        """,
        run_id,
    )
    return [dict(x) for x in rows]


async def run_state_payload(
    db,
    run_id: UUID,
    character_id: UUID,
    char_svc,
) -> Optional[Dict[str, Any]]:
    run = await db.fetchrow("SELECT * FROM guild_raid_runs WHERE id=$1", run_id)
    if not run:
        return None
    tpl = RAID_TEMPLATES.get(run["template_key"]) or {}
    parts = await participants_for_run(db, run_id)
    signed_up = await _is_signed_up(db, run_id, character_id)
    claimed = await has_bonus_claimed(db, run_id, character_id)
    strikes_today = await _strikes_today(db, run_id, character_id)
    cd = await char_svc.on_cooldown(character_id, "guild_raid_strike") if signed_up else 0

    return {
        "run": dict(run),
        "template": {k: v for k, v in tpl.items() if k != "requires_tech"},
        "participants": parts,
        "leaderboard": await strike_leaderboard(db, run_id),
        "my_signed_up": signed_up,
        "my_strikes_today": strikes_today,
        "strike_cooldown_s": int(cd or 0),
        "my_bonus_claimed": claimed,
        "bonus_available": signed_up and await _bonus_claim_allowed(run) and not claimed,
        "can_strike": (
            signed_up
            and run["status"] == "active"
            and int(run["boss_hp_remaining"] or 0) > 0
            and strikes_today < MAX_STRIKES_PER_CHAR_PER_DAY
            and not cd
        ),
    }


async def enrich_run_row(db, run: Dict[str, Any]) -> Dict[str, Any]:
    """Add display fields for list endpoints."""
    tpl = RAID_TEMPLATES.get(run.get("template_key") or "", {})
    out = dict(run)
    out["template_name"] = tpl.get("name", run.get("template_key"))
    out["participant_count"] = await db.fetchval(
        "SELECT COUNT(*)::int FROM guild_raid_participants WHERE run_id=$1",
        UUID(str(run["id"])),
    )
    return out


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
    out = []
    for x in rows:
        out.append(await enrich_run_row(db, dict(x)))
    return out


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


# Legacy endpoint — officers cancel only; success path is auto-settle on HP 0
async def complete_run(
    db,
    char_svc,
    run_id: UUID,
    _actor_character_id: UUID,
    guild_rank: Optional[str],
    discord_bot: Any = None,
) -> tuple[bool, str]:
    if not can_officer_actions(guild_rank):
        return False, "Raids complete automatically when HP reaches zero. Officers may cancel a stuck raid."
    run = await db.fetchrow("SELECT * FROM guild_raid_runs WHERE id=$1", run_id)
    if not run:
        return False, "Raid not found."
    if run["status"] == "active" and int(run["boss_hp_remaining"] or 0) <= 0:
        return await settle_run(db, char_svc, run_id, discord_bot)
    return False, "Use Strike to reduce raid HP, or Cancel to abort."
