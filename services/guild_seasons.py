"""
╔══════════════════════════════════════════════════════════════════════════════╗
║          services/guild_seasons.py — Guild versus guild                     ║
╚══════════════════════════════════════════════════════════════════════════════╝

Guilds have no opponent. You can join one, fund its research, check in and claim
its quests, but nothing a guild does is ever measured against another guild. A
guild is a co-op buff with a chat channel — the only thing it competes with is
its own previous week, silently.

A season gives guilds someone to beat.

── Derived, not recorded ─────────────────────────────────────────────────────

A guild's score is the sum of what its members did, so it is **computed from
`weekly_scores`**, not written to a separate table.

That is the whole design decision. A parallel `guild_season_scores` table would
need its own write on every kill, its own backfill when someone joins or leaves
a guild, and its own reconciliation when the two disagree — and they would
disagree, because membership changes and history does not. Deriving means a
guild's score is correct by construction and a member joining mid-season brings
their weeks with them, which is also the more interesting behaviour: recruiting
matters.

The cost is that the query aggregates rather than reads a counter. That is fine
at this scale — one grouped scan of a table with one row per active character
per week — and the correctness is worth far more than the microseconds.

── Seasons are calendar months ───────────────────────────────────────────────

Long enough that one good night does not decide it and a guild has to sustain
effort; short enough that a guild which starts badly is not locked out for a
quarter. A month also needs no configuration, no admin action to roll over, and
no "when does it end" ambiguity — everyone already knows.

── On rewards ────────────────────────────────────────────────────────────────

Standings, the champion record and the history are here. Gold or item payouts
are deliberately NOT invented: any number picked here would inject currency into
an economy whose measured problem is having too much of it, and choosing that
number is a game-design call for the owner rather than something to slip into a
feature commit. The champion is recorded so a reward can be attached later
without rebuilding any of this.
"""

from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from services.leaderboards import METRICS, normalize_metric

#: How many guilds a standings page returns.
STANDINGS_SIZE = 20


def season_key(when: Optional[datetime] = None) -> str:
    """`YYYY-MM` — the season a moment belongs to."""
    now = when or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    now = now.astimezone(timezone.utc)
    return f"{now.year:04d}-{now.month:02d}"


def season_bounds(when: Optional[datetime] = None) -> Dict[str, Any]:
    """First and last day of the season containing `when`, plus its key.

    `end` is exclusive — the first day of the next month — so a range test is
    `>= start AND < end` and no day is ever double-counted or dropped.
    """
    now = when or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    now = now.astimezone(timezone.utc)

    start = date(now.year, now.month, 1)
    end = date(now.year + 1, 1, 1) if now.month == 12 else date(now.year, now.month + 1, 1)
    return {
        "key": f"{now.year:04d}-{now.month:02d}",
        "start": start,
        "end": end,
        "ends_at": datetime(end.year, end.month, end.day, tzinfo=timezone.utc),
    }


def previous_season_key(when: Optional[datetime] = None) -> str:
    b = season_bounds(when)
    prev_day = b["start"] - timedelta(days=1)
    return f"{prev_day.year:04d}-{prev_day.month:02d}"


async def standings(
    db,
    metric: str = "kills",
    *,
    guild_id: Optional[UUID] = None,
    when: Optional[datetime] = None,
    limit: int = STANDINGS_SIZE,
) -> Dict[str, Any]:
    """Guilds ranked by the summed scores of their members this season.

    `contributors` is deliberately included: a guild's rank is a claim about its
    people, and showing how many of them actually fought is what stops a big
    roster from reading as a strong one.
    """
    metric = normalize_metric(metric)
    col = METRICS[metric]["column"]
    b = season_bounds(when)

    rows = await db.fetch(
        f"""
        SELECT g.id, g.name, g.tag, g.guild_level,
               SUM(w.{col})::bigint AS score,
               COUNT(DISTINCT w.character_id)::int AS contributors
        FROM weekly_scores w
        JOIN characters c ON c.id = w.character_id
        JOIN guilds g ON g.id = c.guild_id
        WHERE w.week_start >= $1 AND w.week_start < $2
        GROUP BY g.id, g.name, g.tag, g.guild_level
        HAVING SUM(w.{col}) > 0
        ORDER BY SUM(w.{col}) DESC, g.name ASC
        LIMIT $3
        """,
        b["start"], b["end"], int(max(1, min(limit, 100))),
    )

    entries = [
        {
            "rank": i + 1,
            "guild_id": str(r["id"]),
            "name": r["name"],
            "tag": r["tag"],
            "guild_level": int(r["guild_level"] or 1),
            "score": int(r["score"] or 0),
            "contributors": int(r["contributors"] or 0),
            "is_yours": guild_id is not None and str(r["id"]) == str(guild_id),
        }
        for i, r in enumerate(rows)
    ]

    yours: Optional[Dict[str, Any]] = next((e for e in entries if e["is_yours"]), None)
    if yours is None and guild_id is not None:
        own = await db.fetchrow(
            f"""
            SELECT SUM(w.{col})::bigint AS score,
                   COUNT(DISTINCT w.character_id)::int AS contributors
            FROM weekly_scores w
            JOIN characters c ON c.id = w.character_id
            WHERE c.guild_id = $1 AND w.week_start >= $2 AND w.week_start < $3
            """,
            guild_id, b["start"], b["end"],
        )
        score = int((own or {}).get("score") or 0)
        if score > 0:
            ahead = await db.fetchval(
                f"""
                SELECT COUNT(*) FROM (
                    SELECT c.guild_id
                    FROM weekly_scores w JOIN characters c ON c.id = w.character_id
                    WHERE c.guild_id IS NOT NULL
                      AND w.week_start >= $2 AND w.week_start < $3
                    GROUP BY c.guild_id
                    HAVING SUM(w.{col}) > $1
                ) t
                """,
                score, b["start"], b["end"],
            )
            yours = {
                "rank": int(ahead or 0) + 1,
                "score": score,
                "contributors": int((own or {}).get("contributors") or 0),
                "is_yours": True,
                "off_board": True,
            }
        else:
            yours = {"rank": None, "score": 0, "contributors": 0, "is_yours": True, "off_board": True}

    return {
        "season": b["key"],
        "ends_at": b["ends_at"].isoformat(),
        "metric": metric,
        "metric_label": METRICS[metric]["label"],
        "metrics": [{"key": k, "label": v["label"]} for k, v in METRICS.items()],
        "entries": entries,
        "yours": yours,
    }


async def champion(db, season: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """The recorded winner of a finished season, if one has been sealed."""
    key = season or previous_season_key()
    row = await db.fetchrow(
        """SELECT s.season_key, s.metric, s.score, g.name, g.tag
           FROM guild_season_champions s
           LEFT JOIN guilds g ON g.id = s.guild_id
           WHERE s.season_key = $1""",
        key,
    )
    if not row:
        return None
    return {
        "season": row["season_key"],
        "metric": row["metric"],
        "score": int(row["score"] or 0),
        "name": row["name"],
        "tag": row["tag"],
    }


async def seal_finished_season(db, metric: str = "kills", when: Optional[datetime] = None) -> Optional[Dict[str, Any]]:
    """Record last month's winner, once.

    Idempotent by primary key, so it is safe to call on every boot and on every
    standings request — there is no scheduler in this project, and a season that
    only closes when an admin remembers is a season that does not close.
    """
    key = previous_season_key(when)
    existing = await db.fetchval(
        "SELECT 1 FROM guild_season_champions WHERE season_key = $1", key
    )
    if existing:
        return await champion(db, key)

    # Standings for the month that just ended.
    prev_start = season_bounds(when)["start"] - timedelta(days=1)
    prev = await standings(db, metric, when=datetime(prev_start.year, prev_start.month, 15, tzinfo=timezone.utc), limit=1)
    top = (prev.get("entries") or [None])[0]
    if not top:
        return None

    await db.execute(
        """INSERT INTO guild_season_champions (season_key, guild_id, metric, score)
           VALUES ($1, $2, $3, $4)
           ON CONFLICT (season_key) DO NOTHING""",
        key, UUID(top["guild_id"]), normalize_metric(metric), int(top["score"]),
    )
    return await champion(db, key)
