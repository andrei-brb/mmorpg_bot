"""
╔══════════════════════════════════════════════════════════════════════════════╗
║        services/camp_upgrades.py — Permanent, purchased progression         ║
╚══════════════════════════════════════════════════════════════════════════════╝

The idle cap has always been a constant: ``Settings.IDLE_REWARDS_MAX_HOURS``,
24 hours, the same for a level-2 character and a level-60 one, and nothing a
player does changes it. Anyone who cannot open the app daily simply loses the
overflow, permanently, with no way to buy their way out of it.

That is also a gap in the economy. Gold has almost nowhere to go once you are
geared — the market is player-driven, the vendor sells starter equipment, and
enhancement eventually stops mattering. Gold with no sink inflates.

A purchasable cap fixes both: it is a **permanent** upgrade (so it is worth
saving for), it costs gold (so it drains the supply), and it pays off precisely
for the players the flat cap punished.

── Why ranks rather than a single toggle ─────────────────────────────────────

Each rank costs more and gives less, so there is a natural stopping point and no
rank is ever mandatory. A player who logs in twice a day should buy none of
these; a player who checks in every other day should buy several. Both are
correct, which is what makes it a decision rather than a tax.

The cap is bounded at the top rank on purpose. Uncapped idle income would
eventually out-earn playing, and an idle game that pays better when you do not
play it has stopped being a game.
"""

from typing import Any, Dict, List, Optional

from config.settings import Settings

#: Extra hours and cost per rank. Cumulative: rank 3 means you bought 1, 2 and 3.
#:
#: The hours-per-gold falls at every step (12h/2.5k, then 12h/8k, then 12h/20k,
#: then 12h/45k), so the marginal value drops steadily and stacking every rank
#: is a genuine choice rather than an obvious one.
IDLE_CAP_RANKS: List[Dict[str, int]] = [
    {"rank": 1, "extra_hours": 12, "cost": 2_500},
    {"rank": 2, "extra_hours": 12, "cost": 8_000},
    {"rank": 3, "extra_hours": 12, "cost": 20_000},
    {"rank": 4, "extra_hours": 12, "cost": 45_000},
]

MAX_IDLE_CAP_RANK = len(IDLE_CAP_RANKS)


def base_cap_hours() -> float:
    return float(Settings.IDLE_REWARDS_MAX_HOURS)


def idle_cap_hours(rank: Any) -> float:
    """Total idle cap for a character at this rank.

    Tolerant of nulls and out-of-range values: this feeds the reward maths, and
    a bad row should mean "no upgrade", never a crash or an unbounded cap.
    """
    try:
        r = int(rank or 0)
    except (TypeError, ValueError):
        r = 0
    r = max(0, min(r, MAX_IDLE_CAP_RANK))
    extra = sum(t["extra_hours"] for t in IDLE_CAP_RANKS if t["rank"] <= r)
    return base_cap_hours() + float(extra)


def next_idle_cap_rank(rank: Any) -> Optional[Dict[str, int]]:
    """The rank a character could buy next, or None at the top."""
    try:
        r = int(rank or 0)
    except (TypeError, ValueError):
        r = 0
    for tier in IDLE_CAP_RANKS:
        if tier["rank"] == r + 1:
            return dict(tier)
    return None


def idle_cap_payload(rank: Any) -> Dict[str, Any]:
    """What the Camp screen shows about the cap."""
    nxt = next_idle_cap_rank(rank)
    try:
        r = max(0, min(int(rank or 0), MAX_IDLE_CAP_RANK))
    except (TypeError, ValueError):
        r = 0
    return {
        "rank": r,
        "max_rank": MAX_IDLE_CAP_RANK,
        "cap_hours": idle_cap_hours(r),
        "base_cap_hours": base_cap_hours(),
        "next": (
            {
                "rank": nxt["rank"],
                "cost": nxt["cost"],
                "extra_hours": nxt["extra_hours"],
                "cap_hours_after": idle_cap_hours(nxt["rank"]),
            }
            if nxt
            else None
        ),
    }
