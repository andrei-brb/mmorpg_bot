"""
╔══════════════════════════════════════════════════════════════════════════════╗
║             services/leaderboards.py — Weekly scoreboards                   ║
╚══════════════════════════════════════════════════════════════════════════════╝

The game had no way to compare yourself to anyone. The only leaderboards that
existed were per-encounter — damage inside one guild boss fight
(``guild_boss.leaderboard``), strikes inside one raid run, and top enhancement
levels — none of which answer "how am I doing relative to other people playing
this game".

That is the whole reason to have other players around. Without it, a shared world
is just a market with strangers in it.

── Why weekly, and why an aggregate table ────────────────────────────────────

**Weekly** because an all-time board is decided within a month and then never
changes: the person who started first wins forever, and everyone else is looking
at a wall. A week is short enough that a new player can be on it and long enough
that one lucky evening does not decide it.

**Aggregate rows, not an event log.** The only question anyone asks is "who is
top this week". A log of every kill would grow without bound to answer a question
that four counters answer exactly. Rows are upserted with ON CONFLICT so
recording a kill is one statement and never reads before writing.

── The week boundary is defined once ─────────────────────────────────────────

``week_start`` is Monday 00:00 UTC, computed here. Putting ``date_trunc('week')``
in each query would spread that definition across every call site and quietly
depend on the database's locale for what "week" means.
"""

from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

#: Rankable metrics -> (column, label, how to format the number).
METRICS: Dict[str, Dict[str, str]] = {
    "kills": {"column": "kills", "label": "Kills", "unit": ""},
    "bosses": {"column": "bosses", "label": "Bosses felled", "unit": ""},
    "xp": {"column": "xp_earned", "label": "Experience", "unit": "xp"},
    "gold": {"column": "gold_earned", "label": "Gold earned", "unit": "g"},
}

DEFAULT_METRIC = "kills"

#: How many rows a board returns. Short enough to read on a phone without
#: scrolling, which is where most people will see it.
BOARD_SIZE = 25


def week_start(when: Optional[datetime] = None) -> date:
    """Monday 00:00 UTC of the week containing `when`."""
    now = when or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    now = now.astimezone(timezone.utc)
    return (now - timedelta(days=now.weekday())).date()


def next_reset(when: Optional[datetime] = None) -> datetime:
    """When the current week's board is replaced."""
    start = week_start(when)
    return datetime(start.year, start.month, start.day, tzinfo=timezone.utc) + timedelta(days=7)


def normalize_metric(raw: Any) -> str:
    key = str(raw or "").strip().lower()
    return key if key in METRICS else DEFAULT_METRIC


async def record(
    db,
    character_id: UUID,
    *,
    kills: int = 0,
    bosses: int = 0,
    xp: int = 0,
    gold: int = 0,
) -> None:
    """Add to a character's score for the current week.

    Never raises. This is called from the victory path, and a scoreboard write
    failing must not cost a player their rewards — the board is a nice-to-have
    sitting behind something that is not.
    """
    if kills <= 0 and bosses <= 0 and xp <= 0 and gold <= 0:
        return
    try:
        await db.execute(
            """
            INSERT INTO weekly_scores (character_id, week_start, kills, bosses, xp_earned, gold_earned)
            VALUES ($1, $2, $3, $4, $5, $6)
            ON CONFLICT (character_id, week_start) DO UPDATE SET
                kills       = weekly_scores.kills       + EXCLUDED.kills,
                bosses      = weekly_scores.bosses      + EXCLUDED.bosses,
                xp_earned   = weekly_scores.xp_earned   + EXCLUDED.xp_earned,
                gold_earned = weekly_scores.gold_earned + EXCLUDED.gold_earned,
                updated_at  = NOW()
            """,
            character_id, week_start(), int(max(0, kills)), int(max(0, bosses)),
            int(max(0, xp)), int(max(0, gold)),
        )
    except Exception:
        import logging

        logging.getLogger("leaderboards").debug("weekly score write failed", exc_info=True)


#: Who a board is drawn from.
#:
#: `friends` is the one that actually motivates people. You will never be rank 1
#: of the world and you know it, but you might beat the person who talked you
#: into playing — and that is a race you can win this week.
SCOPES = ("world", "friends", "guild")
DEFAULT_SCOPE = "world"


def normalize_scope(raw: Any) -> str:
    key = str(raw or "").strip().lower()
    return key if key in SCOPES else DEFAULT_SCOPE


async def board(
    db,
    metric: str = DEFAULT_METRIC,
    *,
    character_id: Optional[UUID] = None,
    scope: str = DEFAULT_SCOPE,
    limit: int = BOARD_SIZE,
) -> Dict[str, Any]:
    """Top players this week, plus where the viewer sits.

    The viewer's own rank is included even when they are off the bottom of the
    board. A leaderboard that only shows the top 25 tells 99% of players nothing
    about themselves, which is the opposite of the point.
    """
    metric = normalize_metric(metric)
    scope = normalize_scope(scope)
    col = METRICS[metric]["column"]
    ws = week_start()

    # Scope is a fixed clause chosen from a closed set, never interpolated user
    # input — same rule as the metric column.
    where = ""
    params: List[Any] = [ws]
    if scope in ("friends", "guild") and character_id is not None:
        if scope == "friends":
            where = """
              AND (c.player_id IN (
                    SELECT CASE WHEN f.player_a_id = me.player_id THEN f.player_b_id
                                ELSE f.player_a_id END
                    FROM player_friendships f, characters me
                    WHERE me.id = $2
                      AND (f.player_a_id = me.player_id OR f.player_b_id = me.player_id)
                  )
                  OR c.id = $2)
            """
        else:
            where = """
              AND c.guild_id IS NOT NULL
              AND c.guild_id = (SELECT guild_id FROM characters WHERE id = $2)
            """
        params.append(character_id)
    params.append(int(max(1, min(limit, 100))))
    limit_ph = f"${len(params)}"

    rows = await db.fetch(
        f"""
        SELECT c.id, c.name, c.level, c.class, c.prestige, g.tag AS guild_tag,
               w.{col} AS score
        FROM weekly_scores w
        JOIN characters c ON c.id = w.character_id
        LEFT JOIN guilds g ON g.id = c.guild_id
        WHERE w.week_start = $1 AND w.{col} > 0
        {where}
        ORDER BY w.{col} DESC, c.name ASC
        LIMIT {limit_ph}
        """,
        *params,
    )

    entries = [
        {
            "rank": i + 1,
            "character_id": str(r["id"]),
            "name": r["name"],
            "level": int(r["level"] or 1),
            "class": r["class"],
            "prestige": int(r["prestige"] or 0),
            "guild_tag": r["guild_tag"],
            "score": int(r["score"] or 0),
            "is_you": character_id is not None and str(r["id"]) == str(character_id),
        }
        for i, r in enumerate(rows)
    ]

    you: Optional[Dict[str, Any]] = next((e for e in entries if e["is_you"]), None)
    # Only computed for the world board. Counting how many friends are ahead of
    # you would need the friend set again; and on a friends board of five people
    # you are never off the bottom anyway.
    if you is None and character_id is not None and scope == "world":
        # Off the board — one extra query rather than fetching every row.
        own = await db.fetchrow(
            f"SELECT {col} AS score FROM weekly_scores WHERE character_id=$1 AND week_start=$2",
            character_id, ws,
        )
        score = int((own or {}).get("score") or 0)
        if score > 0:
            ahead = await db.fetchval(
                f"SELECT COUNT(*) FROM weekly_scores WHERE week_start=$1 AND {col} > $2",
                ws, score,
            )
            you = {"rank": int(ahead or 0) + 1, "score": score, "is_you": True, "off_board": True}
        else:
            you = {"rank": None, "score": 0, "is_you": True, "off_board": True}

    return {
        "metric": metric,
        "scope": scope,
        "scopes": list(SCOPES),
        "metric_label": METRICS[metric]["label"],
        "unit": METRICS[metric]["unit"],
        "metrics": [{"key": k, "label": v["label"]} for k, v in METRICS.items()],
        "week_start": ws.isoformat(),
        "resets_at": next_reset().isoformat(),
        "entries": entries,
        "you": you,
    }
