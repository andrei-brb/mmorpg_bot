"""Daily guild hall check-in: small personal rewards + guild XP."""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, Set, Tuple
from uuid import UUID

from services.character.character_service import CharacterService

log = logging.getLogger("guild.checkin")

CHECKIN_GOLD = 25
CHECKIN_PLAYER_XP = 50
CHECKIN_GUILD_XP = 10


def utc_today() -> date:
    return datetime.now(timezone.utc).date()


def streak_from_dates(dates: Set[date], today: date, checked_today: bool) -> int:
    """Consecutive UTC check-in days ending at today if checked_today, else ending at yesterday."""
    anchor = today if checked_today else today - timedelta(days=1)
    if anchor not in dates:
        return 0
    s = 0
    d = anchor
    while d in dates:
        s += 1
        d -= timedelta(days=1)
    return s


async def _dates_for_character(db, guild_id: UUID, character_id: UUID) -> Set[date]:
    rows = await db.fetch(
        """
        SELECT checkin_day FROM guild_checkins
        WHERE guild_id = $1 AND character_id = $2
        ORDER BY checkin_day DESC
        LIMIT 400
        """,
        guild_id,
        character_id,
    )
    out: Set[date] = set()
    for r in rows:
        d = r["checkin_day"]
        if isinstance(d, date):
            out.add(d)
        else:
            out.add(date.fromisoformat(str(d)[:10]))
    return out


async def checked_today(db, guild_id: UUID, character_id: UUID, today: date) -> bool:
    v = await db.fetchval(
        "SELECT 1 FROM guild_checkins WHERE guild_id=$1 AND character_id=$2 AND checkin_day=$3",
        guild_id,
        character_id,
        today,
    )
    return v is not None


async def count_checked_in_today(db, guild_id: UUID, today: date) -> int:
    v = await db.fetchval(
        """
        SELECT COUNT(DISTINCT character_id)::int FROM guild_checkins
        WHERE guild_id = $1 AND checkin_day = $2
        """,
        guild_id,
        today,
    )
    return int(v or 0)


async def status_payload(db, guild_id: UUID, character_id: UUID) -> Dict[str, Any]:
    today = utc_today()
    checked = await checked_today(db, guild_id, character_id, today)
    days = await _dates_for_character(db, guild_id, character_id)
    streak = streak_from_dates(days, today, checked)
    checked_in_guild_today = await count_checked_in_today(db, guild_id, today)
    return {
        "checked_today": checked,
        "streak": streak,
        "utc_day": today.isoformat(),
        "checked_in_guild_today": checked_in_guild_today,
        "rewards": {"gold": CHECKIN_GOLD, "xp": CHECKIN_PLAYER_XP, "guild_xp": CHECKIN_GUILD_XP},
    }


async def perform_checkin(
    db,
    char_svc: CharacterService,
    guild_id: UUID,
    character_id: UUID,
) -> Tuple[bool, str, Dict[str, Any]]:
    today = utc_today()
    row = await db.fetchrow(
        """
        INSERT INTO guild_checkins (guild_id, character_id, checkin_day)
        VALUES ($1, $2, $3)
        ON CONFLICT (guild_id, character_id, checkin_day) DO NOTHING
        RETURNING id
        """,
        guild_id,
        character_id,
        today,
    )
    if row is None:
        st = await status_payload(db, guild_id, character_id)
        return False, "Already checked in today (UTC).", st

    try:
        await char_svc.add_gold(character_id, CHECKIN_GOLD, "guild_hall_checkin")
        await char_svc.award_xp(character_id, CHECKIN_PLAYER_XP, 1.0)
        from services.guild import guild_tech as guild_tech_mod

        gxp_mult = await guild_tech_mod.checkin_guild_xp_mult(db, guild_id)
        guild_xp_grant = max(1, int(CHECKIN_GUILD_XP * gxp_mult))
        await db.execute(
            "UPDATE guilds SET guild_xp = guild_xp + $2 WHERE id = $1",
            guild_id,
            guild_xp_grant,
        )
    except Exception as e:
        log.exception("guild checkin reward failed: %s", e)
        await db.execute(
            "DELETE FROM guild_checkins WHERE guild_id = $1 AND character_id = $2 AND checkin_day = $3",
            guild_id,
            character_id,
            today,
        )
        return False, "Check-in failed — try again shortly.", await status_payload(db, guild_id, character_id)

    st = await status_payload(db, guild_id, character_id)
    msg = (
        f"Checked in! +{CHECKIN_GOLD} gold, +{CHECKIN_PLAYER_XP} XP, "
        f"+{CHECKIN_GUILD_XP} guild XP (streak {st['streak']} day(s))."
    )
    return True, msg, st
