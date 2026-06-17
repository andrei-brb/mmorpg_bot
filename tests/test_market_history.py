"""Unit tests for market trade history helpers."""

from __future__ import annotations

import unittest
from datetime import datetime, timezone

from services.market.market_history import gold_log_to_history_entry, listing_row_to_history_entry


class TestMarketHistoryHelpers(unittest.TestCase):
    def test_gold_log_market_purchase(self) -> None:
        ent = gold_log_to_history_entry(
            {
                "id": "a",
                "amount": -500,
                "reason": "market purchase",
                "created_at": datetime.now(timezone.utc),
            }
        )
        self.assertIsNotNone(ent)
        assert ent is not None
        self.assertEqual(ent["kind"], "bought")
        self.assertEqual(ent["gold_delta"], -500)

    def test_gold_log_ignores_unrelated(self) -> None:
        self.assertIsNone(
            gold_log_to_history_entry({"id": "b", "amount": 10, "reason": "quest_reward", "created_at": None})
        )

    def test_listing_row_as_buyer(self) -> None:
        from uuid import uuid4

        cid = uuid4()
        ent = listing_row_to_history_entry(
            {
                "id": uuid4(),
                "listing_kind": "fixed",
                "price": 100,
                "current_bid": None,
                "sold_at": datetime.now(timezone.utc),
                "seller_id": uuid4(),
                "buyer_id": cid,
                "item_name": "Iron Sword",
                "seller_name": "Alice",
                "buyer_name": "Bob",
            },
            cid,
        )
        self.assertEqual(ent["kind"], "bought")
        self.assertEqual(ent["item_name"], "Iron Sword")
        self.assertEqual(ent["counterparty_name"], "Alice")


if __name__ == "__main__":
    unittest.main()
