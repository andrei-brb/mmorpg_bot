"""Trade history for Activity market tab — gold_log + completed listings."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional
from uuid import UUID


_MARKET_REASON = re.compile(
    r"(market|auction|bid|outbid|buyout)",
    re.IGNORECASE,
)


def gold_log_to_history_entry(row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    reason = str(row.get("reason") or "").strip()
    if not reason or not _MARKET_REASON.search(reason):
        return None
    amount = int(row.get("amount") or 0)
    kind = _classify_reason(reason, amount)
    return {
        "id": f"gold:{row.get('id')}",
        "at": row.get("created_at"),
        "kind": kind,
        "listing_kind": "auction" if "auction" in reason.lower() else "fixed",
        "item_name": None,
        "gold_delta": amount,
        "detail": reason,
        "counterparty_name": None,
    }


def _classify_reason(reason: str, amount: int) -> str:
    low = reason.lower()
    if "outbid refund" in low or "outbid" in low and amount > 0:
        return "outbid_refund"
    if "buyout" in low:
        return "buyout" if amount < 0 else "sold"
    if "bid" in low:
        return "bid"
    if "market purchase" in low or ("purchase" in low and amount < 0):
        return "bought"
    if "market sale" in low or ("sale" in low and amount > 0):
        return "sold"
    if "refund" in low or "revert" in low:
        return "refund"
    return "trade"


def listing_row_to_history_entry(row: Dict[str, Any], char_id: UUID) -> Dict[str, Any]:
    cid = UUID(str(char_id))
    seller_id = row.get("seller_id")
    buyer_id = row.get("buyer_id")
    listing_kind = str(row.get("listing_kind") or "fixed")
    is_auction = listing_kind == "auction"
    price = int(row.get("current_bid") or row.get("price") or 0)

    if buyer_id and UUID(str(buyer_id)) == cid:
        kind = "bought"
        gold_delta = -price
    elif seller_id and UUID(str(seller_id)) == cid:
        kind = "sold"
        gold_delta = price
    else:
        kind = "trade"
        gold_delta = 0

    counterparty = None
    if kind == "bought" and row.get("seller_name"):
        counterparty = row["seller_name"]
    elif kind == "sold" and row.get("buyer_name"):
        counterparty = row["buyer_name"]

    return {
        "id": f"listing:{row.get('id')}",
        "at": row.get("sold_at") or row.get("listed_at"),
        "kind": kind,
        "listing_kind": listing_kind,
        "item_name": row.get("item_name"),
        "gold_delta": gold_delta,
        "detail": "Auction won" if is_auction and kind == "bought" else (
            "Auction sold" if is_auction and kind == "sold" else (
                "Market purchase" if kind == "bought" else "Market sale"
            )
        ),
        "counterparty_name": counterparty,
    }


async def fetch_trade_history(db, character_id: UUID, *, limit: int = 40) -> List[Dict[str, Any]]:
    """Merged trade history newest-first."""
    limit = max(1, min(int(limit), 80))

    gold_rows = await db.fetch(
        """
        SELECT id, amount, reason, created_at
        FROM gold_log
        WHERE character_id = $1
          AND (
            reason ILIKE '%market%'
            OR reason ILIKE '%auction%'
          )
        ORDER BY created_at DESC
        LIMIT $2
        """,
        character_id,
        limit,
    )

    listing_rows = await db.fetch(
        """
        SELECT ml.id, ml.listing_kind, ml.price, ml.current_bid, ml.sold_at, ml.listed_at,
               ml.seller_id, ml.buyer_id,
               COALESCE(t.name, 'Item') AS item_name,
               seller.name AS seller_name,
               buyer.name AS buyer_name
        FROM market_listings ml
        LEFT JOIN inventory i ON ml.item_id = i.id
        LEFT JOIN item_templates t ON i.template_id = t.id
        LEFT JOIN characters seller ON ml.seller_id = seller.id
        LEFT JOIN characters buyer ON ml.buyer_id = buyer.id
        WHERE (ml.seller_id = $1 OR ml.buyer_id = $1)
          AND ml.sold_at IS NOT NULL
        ORDER BY ml.sold_at DESC
        LIMIT $2
        """,
        character_id,
        limit,
    )

    entries: List[Dict[str, Any]] = []
    seen_at_kind: set[str] = set()

    for r in gold_rows:
        ent = gold_log_to_history_entry(dict(r))
        if ent:
            entries.append(ent)

    for r in listing_rows:
        ent = listing_row_to_history_entry(dict(r), character_id)
        key = f"{ent.get('at')}|{ent.get('kind')}|{ent.get('gold_delta')}"
        if key in seen_at_kind:
            continue
        seen_at_kind.add(key)
        entries.append(ent)

    entries.sort(key=lambda e: str(e.get("at") or ""), reverse=True)
    return entries[:limit]
