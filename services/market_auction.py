"""
Auction listings share `market_listings` with fixed-price rows (`listing_kind`).
Settlement runs periodically (see main.py) and opportunistically from auction HTTP handlers.
"""
from __future__ import annotations

import logging
import math
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from services.character.character_service import CharacterService
from services.character.inventory_service import InventoryService

log = logging.getLogger("market_auction")

MIN_INCREMENT_PCT = 0.05
ANTI_SNIPE = timedelta(minutes=5)


def auction_min_bid(starting: int, current_bid: Optional[int]) -> int:
    s = max(1, int(starting))
    if current_bid is None:
        return s
    c = int(current_bid)
    return max(s, int(math.ceil(c * (1 + MIN_INCREMENT_PCT))))


def maybe_extend_auction_end(auction_ends_at: datetime, now: datetime) -> datetime:
    if auction_ends_at.tzinfo is None:
        auction_ends_at = auction_ends_at.replace(tzinfo=timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    threshold = auction_ends_at - ANTI_SNIPE
    if now >= threshold:
        return max(auction_ends_at, now + ANTI_SNIPE)
    return auction_ends_at


async def settle_expired_auctions(db, limit: int = 40) -> int:
    """Close ended auction listings (no sale) or complete sale to high bidder."""
    rows = await db.fetch(
        """SELECT id FROM market_listings
           WHERE is_active = TRUE AND COALESCE(listing_kind, 'fixed') = 'auction'
             AND auction_ends_at IS NOT NULL AND auction_ends_at <= NOW()
           ORDER BY auction_ends_at ASC
           LIMIT $1""",
        limit,
    )
    settled = 0
    for r in rows:
        if await _settle_one_auction(db, r["id"]):
            settled += 1
    return settled


async def _settle_one_auction(db, listing_id: UUID) -> bool:
    # Lock the listing row for the whole settlement so the loop and any HTTP-triggered
    # settlement can't both pay the seller / deliver the item for the same auction.
    async with db.transaction() as tx:
        locked = await tx.fetchrow(
            """SELECT current_bidder_id FROM market_listings
               WHERE id = $1 AND is_active = TRUE
                 AND COALESCE(listing_kind, 'fixed') = 'auction'
                 AND auction_ends_at IS NOT NULL AND auction_ends_at <= NOW()
               FOR UPDATE""",
            listing_id,
        )
        if not locked:
            return False

        if locked["current_bidder_id"] is None:
            await tx.execute(
                "UPDATE market_listings SET is_active = FALSE WHERE id = $1",
                listing_id,
            )
            return True

        listing = await tx.fetchrow(
            """SELECT ml.*, t.name, i.template_id,
                      i.rarity, i.r_str, i.r_agi, i.r_int, i.r_spi, i.r_sta,
                      i.r_haste, i.r_lifesteal, i.r_resistance, i.r_hit_rating,
                      COALESCE(i.enhancement_level, 0) AS enhancement_level
               FROM market_listings ml
               JOIN inventory i ON ml.item_id = i.id
               JOIN item_templates t ON i.template_id = t.id
               WHERE ml.id = $1 AND ml.current_bid IS NOT NULL""",
            listing_id,
        )
        if not listing:
            # Bidder set but bid/item data missing (e.g. the item row vanished).
            # The winner's gold was escrowed at bid time — refund it before closing,
            # otherwise the escrow is destroyed.
            refund_row = await tx.fetchrow(
                "SELECT current_bidder_id, current_bid FROM market_listings WHERE id = $1",
                listing_id,
            )
            if refund_row and refund_row["current_bidder_id"] and int(refund_row["current_bid"] or 0) > 0:
                await CharacterService(tx).add_gold(
                    refund_row["current_bidder_id"],
                    int(refund_row["current_bid"]),
                    "auction refund: listing data missing at settlement",
                )
                log.error(
                    "Auction settlement refunded winner (missing item data): listing=%s winner=%s amount=%s",
                    listing_id, refund_row["current_bidder_id"], refund_row["current_bid"],
                )
            await tx.execute(
                "UPDATE market_listings SET is_active = FALSE WHERE id = $1",
                listing_id,
            )
            return True

        winner_id = listing["current_bidder_id"]
        pay_amount = int(listing["current_bid"] or 0)
        char_svc = CharacterService(tx)
        inv = InventoryService(tx)
        rarity = listing.get("rarity") or "common"
        bonus = {
            "r_str": listing.get("r_str", 0) or 0,
            "r_agi": listing.get("r_agi", 0) or 0,
            "r_int": listing.get("r_int", 0) or 0,
            "r_spi": listing.get("r_spi", 0) or 0,
            "r_sta": listing.get("r_sta", 0) or 0,
            "r_haste": listing.get("r_haste", 0) or 0,
            "r_lifesteal": listing.get("r_lifesteal", 0) or 0,
            "r_resistance": listing.get("r_resistance", 0) or 0,
            "r_hit_rating": listing.get("r_hit_rating", 0) or 0,
        }
        enhancement_level = listing.get("enhancement_level", 0) or 0

        # Deliver the item first; pay the seller only on success. The winner's gold was
        # already escrowed at bid time, so on failure we refund the winner.
        add_ok, add_msg = await inv.add_item(
            winner_id,
            listing["template_id"],
            rarity=rarity,
            from_="auction",
            bonus=bonus,
            enhancement_level=enhancement_level,
        )
        if not add_ok:
            await char_svc.add_gold(winner_id, pay_amount, "auction refund: inventory full at settlement")
            log.error("Auction settlement failed (inventory): listing=%s winner=%s msg=%s", listing_id, winner_id, add_msg)
            await tx.execute(
                "UPDATE market_listings SET is_active = FALSE WHERE id = $1",
                listing_id,
            )
            return True

        await char_svc.add_gold(listing["seller_id"], pay_amount, "market sale")
        await tx.execute("DELETE FROM inventory WHERE id = $1", listing["item_id"])
        await tx.execute(
            """UPDATE market_listings
               SET is_active = FALSE, sold_at = NOW(), buyer_id = $2
               WHERE id = $1""",
            listing_id,
            winner_id,
        )
        return True
