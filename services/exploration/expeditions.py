"""
╔══════════════════════════════════════════════════════════════════════════════╗
║        services/exploration/expeditions.py — Explore with a purpose         ║
╚══════════════════════════════════════════════════════════════════════════════╝

Exploring is a button that rolls fixed odds: 40% an enemy, 15% a boss, 20% loot,
the rest nothing. Those bands are the same for every player, in every zone, on
every press, and no decision the player makes changes them.

So "explore" means "press again". If you need materials you press until loot
comes up; if you are hunting a boss you press until a boss comes up. The button
is a slot machine and the player is not playing, they are waiting.

An expedition is a declared intent. You say what you came for, and the odds bend
toward it.

── The cost is built into the shape ──────────────────────────────────────────

Every focus REDISTRIBUTES probability, it never adds any. Hunting means more
fights and less loot. Scavenging means more loot and fewer fights, which is less
XP. Nothing here makes exploring strictly better — it makes it answer a
question, and every answer gives something up.

That is also why there is no cost in gold or a cooldown. The trade-off is
already in the odds; charging on top would be paying twice for one choice.

── Bands, not multipliers ────────────────────────────────────────────────────

The roller works on cumulative bands over one random draw. Focuses are expressed
as shifts to those boundaries so the result is always a valid distribution by
construction — it cannot sum to more than 1, and no outcome can be pushed to
zero, because a focus that eliminated an outcome would turn a preference into a
guarantee.
"""

from typing import Any, Dict, List, Optional

#: Nothing may be squeezed below this share. A focus expresses a preference; an
#: outcome at 0% would make it a promise, and a player who hunts for an hour
#: should still occasionally stumble on something.
MIN_BAND = 0.05

#: id -> how it reshapes the roll.
#:
#: `enemy`, `boss` and `loot` are share deltas applied to those outcomes; `safe`
#: absorbs the remainder, so it is the outcome that pays for everything else.
#: Safe is the right bill-payer: it is the one result nobody is exploring FOR.
FOCUSES: Dict[str, Dict[str, Any]] = {
    "wander": {
        "name": "Wander",
        "emoji": "🧭",
        "description": "No particular aim. The odds as they have always been.",
        "enemy": 0.0,
        "boss": 0.0,
        "loot": 0.0,
    },
    "hunt": {
        "name": "Hunt",
        "emoji": "⚔️",
        "description": "Look for a fight. More enemies, less of everything else.",
        "enemy": +0.20,
        "boss": 0.0,
        "loot": -0.08,
    },
    "stalk": {
        "name": "Stalk",
        "emoji": "💀",
        "description": "Track something big. Far more bosses, fewer ordinary fights.",
        "enemy": -0.15,
        "boss": +0.12,
        "loot": -0.05,
    },
    "scavenge": {
        "name": "Scavenge",
        "emoji": "🎒",
        "description": "Comb the ground. More finds, fewer fights — and less experience.",
        "enemy": -0.18,
        "boss": -0.05,
        "loot": +0.22,
    },
}

DEFAULT_FOCUS = "wander"


def normalize(raw: Any) -> str:
    key = str(raw or "").strip().lower()
    return key if key in FOCUSES else DEFAULT_FOCUS


def catalog() -> List[Dict[str, Any]]:
    """Every focus, for the pre-explore picker.

    `shifts` is included so the UI can show what a choice actually does rather
    than making the player infer it from flavour text.
    """
    return [
        {
            "id": key,
            "name": f["name"],
            "emoji": f["emoji"],
            "description": f["description"],
            "shifts": {
                "enemy": int(round(f["enemy"] * 100)),
                "boss": int(round(f["boss"] * 100)),
                "loot": int(round(f["loot"] * 100)),
            },
        }
        for key, f in FOCUSES.items()
    ]


def apply_to_bands(
    focus: str,
    *,
    enemy: float,
    boss: float,
    loot: float,
) -> Dict[str, float]:
    """Reshape the three targeted shares; `safe` takes whatever is left.

    Returns shares (not cumulative boundaries) that are guaranteed to be
    individually at least ``MIN_BAND`` and to total at most 1.0.
    """
    f = FOCUSES[normalize(focus)]

    shares = {
        "enemy": max(MIN_BAND, enemy + float(f["enemy"])),
        "boss": max(MIN_BAND, boss + float(f["boss"])),
        "loot": max(MIN_BAND, loot + float(f["loot"])),
    }

    # Safe pays the bill. If the three targeted outcomes have grown past what is
    # available, scale them back proportionally so safe keeps its floor — a
    # distribution that summed past 1.0 would silently truncate the last band.
    budget = 1.0 - MIN_BAND
    total = sum(shares.values())
    if total > budget:
        scale = budget / total
        shares = {k: max(MIN_BAND, v * scale) for k, v in shares.items()}
        # Re-check: the floors themselves may now exceed the budget, which can
        # only happen if MIN_BAND is set absurdly high relative to the outcomes.
        total = sum(shares.values())
        if total > budget:
            shares = {k: budget / len(shares) for k in shares}

    shares["safe"] = max(0.0, 1.0 - sum(shares.values()))
    return shares


def describe(focus: str) -> Optional[Dict[str, Any]]:
    key = normalize(focus)
    f = FOCUSES[key]
    return {"id": key, "name": f["name"], "emoji": f["emoji"], "description": f["description"]}
