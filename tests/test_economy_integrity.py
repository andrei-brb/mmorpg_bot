"""Regression tests for the economy atomicity fixes (anti-dupe / anti-gold-loss)."""

from __future__ import annotations

import pathlib
import unittest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from services.character.character_service import CharacterService

ROOT = pathlib.Path(__file__).resolve().parents[1]


class TestGoldHelpersAtomic(unittest.IsolatedAsyncioTestCase):
    """add_gold / deduct_gold must be single atomic UPDATEs (no read-modify-write race)."""

    async def test_deduct_gold_is_single_conditional_update(self) -> None:
        db = MagicMock()
        db.fetchval = AsyncMock(return_value=50)  # UPDATE ... RETURNING new balance
        db.execute = AsyncMock()
        ok = await CharacterService(db).deduct_gold(uuid4(), 10, "test")
        self.assertTrue(ok)
        sql = db.fetchval.await_args_list[0][0][0]
        self.assertIn("gold = gold - $2", sql)
        self.assertIn("gold >= $2", sql)  # conditional guard prevents overspend/negative
        self.assertEqual(db.execute.await_count, 1)  # gold_log written exactly once

    async def test_deduct_gold_insufficient_returns_false_and_logs_nothing(self) -> None:
        db = MagicMock()
        db.fetchval = AsyncMock(return_value=None)  # WHERE gold >= $2 matched no row
        db.execute = AsyncMock()
        ok = await CharacterService(db).deduct_gold(uuid4(), 10**9, "test")
        self.assertFalse(ok)
        self.assertEqual(db.execute.await_count, 0)

    async def test_add_gold_is_single_increment_update(self) -> None:
        db = MagicMock()
        db.fetchval = AsyncMock(return_value=110)
        db.execute = AsyncMock()
        await CharacterService(db).add_gold(uuid4(), 10, "test")
        sql = db.fetchval.await_args_list[0][0][0]
        self.assertIn("gold = gold + $2", sql)


class TestMarketSourceInvariants(unittest.TestCase):
    """Guard the transaction/locking structure so a refactor can't silently
    reintroduce the duplication race that these fixes closed."""

    @staticmethod
    def _src(rel: str) -> str:
        return (ROOT / rel).read_text()

    def test_slash_market_buy_locks_listing_in_txn(self) -> None:
        src = self._src("cogs/economy/economy_cog.py")
        self.assertIn("db.transaction()", src)
        self.assertIn("FOR UPDATE OF ml", src)

    def test_http_market_buy_locks_listing_in_txn(self) -> None:
        src = self._src("services/activity_http.py")
        self.assertIn("FOR UPDATE OF ml", src)

    def test_market_sell_guards_duplicate_listing(self) -> None:
        src = self._src("cogs/economy/economy_cog.py")
        self.assertIn("already listed", src.lower())

    def test_auction_settlement_locks_in_txn(self) -> None:
        src = self._src("services/market_auction.py")
        self.assertIn("db.transaction()", src)
        self.assertIn("FOR UPDATE", src)


if __name__ == "__main__":
    unittest.main()
