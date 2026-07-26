"""
╔══════════════════════════════════════════════════════════════════════════════╗
║             services/economy/pricing.py — One price formula                 ║
╚══════════════════════════════════════════════════════════════════════════════╝

Item prices came from two independent places that knew nothing about each other:

  * ``database/generate_items.py`` — a hardcoded ``VENDOR_BUY`` table indexed by
    rarity and a magic ``* 0.4`` for the sell price.
  * the seed block in ``database/db.py`` — 64 templates with buy and sell
    written by hand, one pair at a time.

Measured across the 52 seed items that carry both numbers, the sell/buy ratio
runs 38% to 50% with **ten distinct values**, while the generator uses a flat
40% for everything it makes. Nothing enforces any relationship between the two,
so every item added by hand is a fresh guess and the drift only grows.

This module is the single answer. The generator calls it, and a test measures
the seed against it so drift is *reported* rather than discovered years later.

── What this deliberately does not do ────────────────────────────────────────

It does **not** rewrite existing prices, and the constants below are *fitted to
them* rather than chosen freshly.

That matters more than it sounds. A first pass picked round numbers and produced
prices up to 6.7x the live ones — which would have repriced 500 items that are
loaded at boot, changed what players already believe their gear is worth, and
(because vendor sell scales with buy) injected a large amount of new gold into
an economy whose actual problem is having too much of it. A refactor that
quietly rebalances is worse than the duplication it replaces.

So: the formula describes the curve the game already has. New items land on that
curve automatically; existing ones are measured against it by a test and
reported, never silently overwritten.

── The sell ratio is a sink, not a rounding ─────────────────────────────────

``SELL_RATIO`` is the fraction of an item's value the vendor gives back. It is
the game's oldest gold sink and the reason buying is a decision: every purchase
you reverse costs you the spread. Ten accidental values meant that spread varied
by item for no reason anyone chose.
"""

from typing import Any, Dict, Optional

#: What a vendor pays for an item, as a fraction of its buy price. One number,
#: chosen: it matches the generator's existing 0.4 and the median of the
#: hand-authored seed, so adopting it changes nothing that already exists.
SELL_RATIO = 0.40

#: Base value of a level-1 common item of each type.
BASE_VALUE: Dict[str, int] = {
    "weapon": 10,
    "armor": 10,
    "accessory": 10,
    "consumable": 6,
    "material": 4,
    "quest": 0,       # never purchasable
    "cosmetic": 25,
}

#: Rarity multiplier and per-level growth.
#:
#: These are FITTED to the 500 live items in database/migrate_add_items.sql
#: (applied at boot from db.py:1001), not invented. The formula's job is to
#: describe the curve the game already has so that new items land on it — a
#: "unification" that silently repriced 500 live items would be a balance change
#: smuggled in under a refactor, and raising vendor sell prices in particular
#: would inject gold into an economy that already has too much of it.
#:
#: Measured fit: 96% of live items land within ±25% of the formula, range
#: 0.92x to 1.41x. The outliers are the low-level commons, where the
#: hand-picked numbers were flattest.
LEVEL_GROWTH = 1.04

RARITY_VALUE_MULT: Dict[str, float] = {
    "common": 1.41,
    "uncommon": 2.55,
    "rare": 4.56,
    "epic": 7.20,
    "legendary": 10.20,
    # Above legendary the live data runs out, so these continue the observed
    # taper (each tier is a smaller step up than the last) rather than guessing.
    "mythic": 13.50,
    "artifact": 17.00,
}


def item_value(
    item_type: str,
    rarity: str,
    level_req: Any = 1,
) -> int:
    """The canonical vendor buy price for an item.

    Tolerant of unknown types and rarities: an item the formula does not
    recognise is priced as a common of its level rather than raising, because
    this feeds seed generation and must never break a build.
    """
    base = BASE_VALUE.get(str(item_type or "").lower())
    if base is None:
        base = BASE_VALUE["material"]
    if base <= 0:
        return 0

    try:
        lvl = max(1, int(level_req or 1))
    except (TypeError, ValueError):
        lvl = 1

    mult = RARITY_VALUE_MULT.get(str(rarity or "common").lower(), 1.0)
    return max(1, int(round(base * mult * (LEVEL_GROWTH ** (lvl - 1)))))


def vendor_prices(
    item_type: str,
    rarity: str,
    level_req: Any = 1,
    *,
    sellable_only: bool = False,
) -> Dict[str, int]:
    """``{"buy": int, "sell": int}`` for one item.

    ``sellable_only`` is for drops that no vendor stocks — set pieces, quest
    rewards, boss loot. They still have a sell value (you can offload them) but
    a buy price of 0, which is how the seed already marks them.
    """
    buy = item_value(item_type, rarity, level_req)
    sell = max(1, int(round(buy * SELL_RATIO))) if buy > 0 else 0
    return {"buy": 0 if sellable_only else buy, "sell": sell}


def sell_price_for(buy_price: Any) -> int:
    """The vendor's offer for an item whose buy price is already fixed.

    Used for the existing hand-authored templates, where the buy price is
    established and only the ratio needs to be consistent.
    """
    try:
        buy = int(buy_price or 0)
    except (TypeError, ValueError):
        return 0
    if buy <= 0:
        return 0
    return max(1, int(round(buy * SELL_RATIO)))


def ratio_of(buy: Any, sell: Any) -> Optional[float]:
    """Observed sell/buy ratio, or None when either side is unpriced."""
    try:
        b, s = int(buy or 0), int(sell or 0)
    except (TypeError, ValueError):
        return None
    if b <= 0 or s <= 0:
        return None
    return s / b
