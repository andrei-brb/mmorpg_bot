"""
╔══════════════════════════════════════════════════════════════════════════════╗
║         services/trade/trade_service.py — Safe P2P Trading (anti-dupe)      ║
╚══════════════════════════════════════════════════════════════════════════════╝

Every accept runs inside a single db.transaction():
  1. Lock the trade row FOR UPDATE (state='open', not expired)
  2. Lock the offered inventory row FOR UPDATE and re-validate it
  3. Conditionally deduct the buyer's gold (WHERE gold >= $ guard; 0 gold = gift)
  4. Transfer item ownership to the buyer
  5. Credit the seller (gold_log rows written for both sides, reason 'trade')
  6. Flip the trade row with a conditional UPDATE (state='open') — a lost flip
     aborts and rolls back everything, so double-accepts are impossible.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from config.settings import Settings
from services.character.character_service import CharacterService

log = logging.getLogger("trade_service")


class TradeAbort(Exception):
    """Raised inside a trade transaction to roll it back with a user-facing message."""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class TradeService:
    MAX_OPEN_OUTGOING = 3

    # Item must still be owned by the seller, unequipped, unlocked, not soulbound,
    # tradeable, and not actively listed on the market (same ml.is_active join that
    # InventoryService.get_all uses to hide listed items).
    _ITEM_SQL = """
        SELECT i.id, i.character_id, i.is_equipped, i.locked, i.quantity,
               t.name, t.icon, t.soulbound, t.tradeable,
               COALESCE(i.rarity, t.rarity) AS rarity,
               ml.id AS active_listing_id
        FROM inventory i
        JOIN item_templates t ON i.template_id = t.id
        LEFT JOIN market_listings ml ON i.id = ml.item_id AND ml.is_active = TRUE
        WHERE i.id = $1 AND i.character_id = $2
        FOR UPDATE OF i
    """

    def __init__(self, db):
        self.db = db

    # ── Lazy expiry (called on any /trade command) ────────────────────────────

    async def expire_stale(self) -> None:
        await self.db.execute(
            "UPDATE trades SET state='expired', resolved_at=NOW() "
            "WHERE state='open' AND expires_at < NOW()"
        )

    # ── Validation ────────────────────────────────────────────────────────────

    @staticmethod
    def _item_error(item: Optional[Any]) -> Optional[str]:
        """Return a user-facing reason the item can't be traded, or None if OK."""
        if not item:
            return "the item is no longer in the sender's bag"
        if item.get("is_equipped"):
            return "the item is equipped — unequip it first"
        if item.get("locked"):
            return "the item is locked"
        if item.get("soulbound"):
            return "soulbound items cannot be traded"
        if item.get("tradeable") is False:
            return "this item cannot be traded"
        if item.get("active_listing_id"):
            return "the item is listed on the market"
        return None

    # ── Offers ────────────────────────────────────────────────────────────────

    async def create_offer(
        self, from_char_id: UUID, to_char_id: UUID, item_id: UUID, gold_ask: int
    ) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        if from_char_id == to_char_id:
            return False, "You can't trade with yourself.", None
        if gold_ask < 0:
            return False, "Gold ask can't be negative.", None

        # Lock the item FOR UPDATE so validation + insert are atomic — the same
        # item can't slip into two open offers (or an offer + a market listing).
        try:
            async with self.db.transaction() as tx:
                open_count = await tx.fetchval(
                    "SELECT COUNT(*) FROM trades "
                    "WHERE from_character=$1 AND state='open' AND expires_at > NOW()",
                    from_char_id,
                )
                if int(open_count or 0) >= self.MAX_OPEN_OUTGOING:
                    raise TradeAbort(
                        f"You already have **{self.MAX_OPEN_OUTGOING}** open outgoing offers. "
                        "Cancel one with `/trade cancel` first."
                    )

                item = await tx.fetchrow(self._ITEM_SQL, item_id, from_char_id)
                err = self._item_error(item)
                if err:
                    raise TradeAbort(f"Can't offer this item: {err}.")

                dup = await tx.fetchval(
                    "SELECT 1 FROM trades WHERE item_id=$1 AND state='open' AND expires_at > NOW()",
                    item_id,
                )
                if dup:
                    raise TradeAbort("That item is already in an open trade offer.")

                trade = await tx.fetchrow(
                    """INSERT INTO trades(from_character, to_character, item_id, gold_ask)
                       VALUES($1, $2, $3, $4) RETURNING *""",
                    from_char_id, to_char_id, item_id, int(gold_ask),
                )
                payload = {
                    **dict(trade),
                    "item_name": item["name"],
                    "item_icon": item.get("icon"),
                    "rarity": item.get("rarity") or "common",
                }
                return True, f"Offer created for **{item['name']}**.", payload
        except TradeAbort as e:
            return False, e.message, None

    async def list_for(self, char_id: UUID) -> List[Dict[str, Any]]:
        rows = await self.db.fetch(
            """SELECT tr.*, t.name AS item_name, t.icon AS item_icon,
                      cf.name AS from_name, ct.name AS to_name
               FROM trades tr
               JOIN inventory i ON tr.item_id = i.id
               JOIN item_templates t ON i.template_id = t.id
               JOIN characters cf ON tr.from_character = cf.id
               JOIN characters ct ON tr.to_character = ct.id
               WHERE (tr.from_character=$1 OR tr.to_character=$1)
                 AND tr.state='open' AND tr.expires_at > NOW()
               ORDER BY tr.created_at DESC""",
            char_id,
        )
        return [dict(r) for r in rows]

    async def cancel(self, trade_id: UUID, from_char_id: UUID) -> Tuple[bool, str]:
        """Sender cancels their own open offer (conditional UPDATE — no races)."""
        res = await self.db.execute(
            "UPDATE trades SET state='cancelled', resolved_at=NOW() "
            "WHERE id=$1 AND from_character=$2 AND state='open'",
            trade_id, from_char_id,
        )
        if str(res).strip() != "UPDATE 1":
            return False, "No open offer of yours with that ID (already resolved or expired?)."
        return True, "Trade offer cancelled."

    async def decline(self, trade_id: UUID, to_char_id: UUID) -> Tuple[bool, str]:
        """Target declines an offer addressed to them (conditional UPDATE)."""
        res = await self.db.execute(
            "UPDATE trades SET state='cancelled', resolved_at=NOW() "
            "WHERE id=$1 AND to_character=$2 AND state='open'",
            trade_id, to_char_id,
        )
        if str(res).strip() != "UPDATE 1":
            return False, "This offer is no longer open."
        return True, "Trade offer declined."

    # ── Accept (the dupe-critical path) ───────────────────────────────────────

    async def accept(
        self, trade_id: UUID, actor_char_id: UUID
    ) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """
        Atomically settle a trade. Any failure raises TradeAbort inside the
        transaction, which rolls back gold, item, and state together.
        """
        try:
            async with self.db.transaction() as tx:
                # Lock the trade row so concurrent accepts serialize here; the
                # WHERE state='open' predicate is re-checked after the lock waits.
                trade = await tx.fetchrow(
                    "SELECT * FROM trades "
                    "WHERE id=$1 AND state='open' AND expires_at > NOW() FOR UPDATE",
                    trade_id,
                )
                if not trade:
                    raise TradeAbort("Trade not found, already resolved, or expired.")
                if trade["to_character"] != actor_char_id:
                    raise TradeAbort("This trade offer isn't addressed to you.")

                seller_id = trade["from_character"]
                buyer_id = trade["to_character"]
                gold_ask = int(trade["gold_ask"] or 0)

                # 1) Lock the offered inventory row FOR UPDATE and re-validate.
                item = await tx.fetchrow(self._ITEM_SQL, trade["item_id"], seller_id)
                err = self._item_error(item)
                if err:
                    raise TradeAbort(f"Trade is no longer valid: {err}.")

                # Enforce the same bag cap add_item applies on every other
                # item-acquisition path (market buys are rejected+refunded when full).
                player_row = await tx.fetchrow(
                    """SELECT p.is_premium FROM players p
                       JOIN characters c ON c.player_id=p.id WHERE c.id=$1""",
                    buyer_id,
                )
                max_slots = (
                    Settings.PREMIUM_INVENTORY_SLOTS
                    if (player_row and player_row["is_premium"])
                    else Settings.FREE_INVENTORY_SLOTS
                )
                bag_count = await tx.fetchval(
                    "SELECT COUNT(*) FROM inventory "
                    "WHERE character_id=$1 AND COALESCE(is_equipped,FALSE)=FALSE",
                    buyer_id,
                )
                if int(bag_count or 0) >= max_slots:
                    raise TradeAbort(
                        f"Your bag is full ({bag_count}/{max_slots}) — make room first."
                    )

                char_svc = CharacterService(tx)

                # 2) Conditional gold deduct (WHERE gold >= $ guard inside
                #    deduct_gold). 0-gold trades are gifts — nothing to deduct.
                if gold_ask > 0:
                    paid = await char_svc.deduct_gold(buyer_id, gold_ask, "trade")
                    if not paid:
                        raise TradeAbort(f"You need **{gold_ask:,}**🪙 to accept this trade.")

                # 3) Transfer item ownership to the buyer.
                await tx.execute(
                    "UPDATE inventory SET character_id=$2, is_equipped=FALSE, equip_slot=NULL "
                    "WHERE id=$1",
                    trade["item_id"], buyer_id,
                )

                # 4) Credit the seller (writes the seller-side gold_log row).
                if gold_ask > 0:
                    await char_svc.add_gold(seller_id, gold_ask, "trade")

                # 5) Conditional state flip — if another accept won, this matches
                #    0 rows and the whole transaction rolls back (no dupes).
                res = await tx.execute(
                    "UPDATE trades SET state='accepted', resolved_at=NOW() "
                    "WHERE id=$1 AND state='open'",
                    trade["id"],
                )
                if str(res).strip() != "UPDATE 1":
                    raise TradeAbort("This trade was already resolved.")

                payload = {
                    "item_name": item["name"],
                    "item_icon": item.get("icon"),
                    "rarity": item.get("rarity") or "common",
                    "gold_ask": gold_ask,
                    "from_character": seller_id,
                    "to_character": buyer_id,
                }
                if gold_ask > 0:
                    msg = f"You received **{item['name']}** for **{gold_ask:,}**🪙."
                else:
                    msg = f"You received **{item['name']}** as a gift!"
                return True, msg, payload
        except TradeAbort as e:
            return False, e.message, None
