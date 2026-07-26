"""Item set bonuses — one definition, used by both the stat maths and the API.

The bonuses were previously inline in CharacterService.get_derived_stats, which
meant the numbers a player is *given* and the numbers we could *show* them had
no shared source. Anything displayed would have been a second copy, free to
drift. This module is the single definition; the stat computation reads it, and
so does the endpoint that renders it.

Content note: the tiers go 2 / 4 / 6, but every set currently in the database
has exactly four pieces, so the 6-piece tier is unreachable today. It is kept
because the threshold is real and adding pieces is a content change, not a code
one — but SET_TIERS is what a designer should edit, and `max_pieces` in the API
payload tells the client which tiers are actually attainable.
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

# Bonus granted at each piece count. Cumulative-by-threshold, NOT additive: a
# player at 4 pieces gets the 4-piece row only, matching the original
# if/elif ordering in get_derived_stats.
SET_TIERS: List[Dict[str, Any]] = [
    {
        "pieces": 2,
        "stats": {"armor": 15},
        "description": "+15 armour",
    },
    {
        "pieces": 4,
        "stats": {"strength": 10, "agility": 10, "intellect": 10},
        "description": "+10 to strength, agility and intellect",
    },
    {
        "pieces": 6,
        "stats": {"strength": 15, "agility": 15, "intellect": 15, "armor": 30},
        "description": "+15 to strength, agility and intellect, +30 armour",
    },
]

# Display names. A set_id with no entry falls back to a title-cased slug, so a
# designer adding a set to the database gets something readable immediately
# rather than a raw identifier leaking into the UI.
SET_NAMES: Dict[str, str] = {
    "blackrock_warplate": "Blackrock Warplate",
    "gravewalker": "Gravewalker",
}


def set_display_name(set_id: str) -> str:
    if not set_id:
        return ""
    known = SET_NAMES.get(set_id)
    if known:
        return known
    return set_id.replace("_", " ").title()


def active_tier(piece_count: int) -> Optional[Dict[str, Any]]:
    """The single tier in effect at this piece count, or None below the first."""
    best: Optional[Dict[str, Any]] = None
    for tier in SET_TIERS:
        if piece_count >= tier["pieces"]:
            best = tier
    return best


def next_tier(piece_count: int, max_pieces: Optional[int] = None) -> Optional[Dict[str, Any]]:
    """The next tier a player could still reach.

    `max_pieces` (how many pieces the set actually contains) filters out tiers
    that cannot be achieved — without it we would tell a player wearing all four
    pieces of a four-piece set that they are "2 away" from a sixth.
    """
    for tier in SET_TIERS:
        if piece_count < tier["pieces"]:
            if max_pieces is not None and tier["pieces"] > max_pieces:
                return None
            return tier
    return None


def apply_set_bonuses(stats: Dict[str, int], set_counts: Dict[str, int]) -> None:
    """Add every active set bonus into `stats`, in place."""
    for count in set_counts.values():
        tier = active_tier(int(count or 0))
        if not tier:
            continue
        for key, value in tier["stats"].items():
            stats[key] = stats.get(key, 0) + value


def summarize_sets(
    equipped_set_ids: Iterable[Optional[str]],
    set_sizes: Optional[Dict[str, int]] = None,
) -> List[Dict[str, Any]]:
    """Player-facing view of the sets a character is currently wearing.

    `set_sizes` maps set_id -> how many pieces exist in the world, so the client
    can render "3 / 4" and know which tiers remain reachable.
    """
    counts: Dict[str, int] = {}
    for sid in equipped_set_ids:
        if not sid:
            continue
        counts[sid] = counts.get(sid, 0) + 1

    out: List[Dict[str, Any]] = []
    for set_id, count in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])):
        max_pieces = (set_sizes or {}).get(set_id)
        cur = active_tier(count)
        nxt = next_tier(count, max_pieces)
        out.append(
            {
                "set_id": set_id,
                "name": set_display_name(set_id),
                "equipped": count,
                "max_pieces": max_pieces,
                "active_tier": cur["pieces"] if cur else 0,
                "active_bonus": cur["description"] if cur else None,
                "next_tier": nxt["pieces"] if nxt else None,
                "next_bonus": nxt["description"] if nxt else None,
                "pieces_to_next": (nxt["pieces"] - count) if nxt else None,
            }
        )
    return out
