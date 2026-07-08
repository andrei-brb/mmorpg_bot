"""Regression tests for the P2P trading system (dupe/gold-loss safety)."""

from __future__ import annotations

import pathlib
import unittest
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from services.trade.trade_service import TradeService

ROOT = pathlib.Path(__file__).resolve().parents[1]

SELLER = uuid4()
BUYER = uuid4()
ITEM = uuid4()
TRADE = uuid4()


def _trade_row(gold_ask=100):
    return {
        "id": TRADE,
        "from_character": SELLER,
        "to_character": BUYER,
        "item_id": ITEM,
        "gold_ask": gold_ask,
        "state": "open",
    }


def _item_row(**over):
    row = {
        "id": ITEM,
        "character_id": SELLER,
        "is_equipped": False,
        "locked": False,
        "quantity": 1,
        "name": "Iron Sword",
        "icon": "🗡️",
        "soulbound": False,
        "tradeable": True,
        "rarity": "common",
        "active_listing_id": None,
    }
    row.update(over)
    return row


class _Tx:
    """Mock transaction connection. In the real code, raising TradeAbort inside
    the db.transaction() block rolls back every statement recorded here."""

    def __init__(self, *, trade_row, item_row, deduct_result=900, flip_result="UPDATE 1"):
        self._trade_row = trade_row
        self._item_row = item_row
        self._deduct_result = deduct_result
        self._flip_result = flip_result
        self.executed_sql: list[str] = []
        self.fetchrow = AsyncMock(side_effect=self._fetchrow)
        self.fetchval = AsyncMock(side_effect=self._fetchval)
        self.execute = AsyncMock(side_effect=self._execute)

    def _fetchrow(self, sql, *args):
        if "FROM trades" in sql:
            return self._trade_row
        if "FROM inventory i" in sql:
            return self._item_row
        return None

    def _fetchval(self, sql, *args):
        if "gold = gold - $2" in sql:  # buyer deduct (conditional WHERE gold >= $2)
            return self._deduct_result
        if "gold = gold + $2" in sql:  # seller credit
            return 1000
        if "COUNT(*)" in sql:  # buyer bag-capacity check
            return 0
        return None

    def gold_fetchvals(self):
        return [c for c in self.fetchval.await_args_list if "gold" in c[0][0]]

    def _execute(self, sql, *args):
        self.executed_sql.append(sql)
        if "state='accepted'" in sql:
            return self._flip_result
        return "INSERT 0 1"


def _svc(tx: _Tx) -> TradeService:
    db = MagicMock()

    @asynccontextmanager
    async def _txn():
        yield tx

    db.transaction = _txn
    db.execute = AsyncMock(return_value="UPDATE 0")
    return TradeService(db)


class TestTradeAccept(unittest.IsolatedAsyncioTestCase):
    async def test_successful_accept_deducts_transfers_credits_and_flips(self):
        tx = _Tx(trade_row=_trade_row(gold_ask=100), item_row=_item_row())
        ok, msg, payload = await _svc(tx).accept(TRADE, BUYER)
        self.assertTrue(ok)
        self.assertIsNotNone(payload)
        # Buyer deducted with the conditional guard
        deduct_sql = tx.gold_fetchvals()[0][0][0]
        self.assertIn("gold >= $2", deduct_sql)
        # Item transferred to the buyer
        transfer = [s for s in tx.executed_sql if "UPDATE inventory SET character_id" in s]
        self.assertEqual(len(transfer), 1)
        # Conditional state flip is the last statement and guards on state='open'
        self.assertIn("state='accepted'", tx.executed_sql[-1])
        self.assertIn("state='open'", tx.executed_sql[-1])

    async def test_insufficient_gold_fails_and_nothing_transfers(self):
        # deduct_gold's WHERE gold >= $2 matched no row -> fetchval returns None
        tx = _Tx(trade_row=_trade_row(gold_ask=10**9), item_row=_item_row(), deduct_result=None)
        ok, msg, payload = await _svc(tx).accept(TRADE, BUYER)
        self.assertFalse(ok)
        self.assertIsNone(payload)
        # No item transfer, no seller credit, no state flip ever issued
        self.assertFalse(any("UPDATE inventory SET character_id" in s for s in tx.executed_sql))
        self.assertFalse(any("state='accepted'" in s for s in tx.executed_sql))
        credit_calls = [c for c in tx.fetchval.await_args_list if "gold = gold + $2" in c[0][0]]
        self.assertEqual(credit_calls, [])

    async def test_double_accept_loses_conditional_flip_and_grants_nothing(self):
        # Another accept already flipped state -> conditional UPDATE matches 0 rows.
        # TradeAbort propagates inside db.transaction(), rolling back gold + item.
        tx = _Tx(trade_row=_trade_row(gold_ask=100), item_row=_item_row(), flip_result="UPDATE 0")
        ok, msg, payload = await _svc(tx).accept(TRADE, BUYER)
        self.assertFalse(ok)
        self.assertIsNone(payload)
        self.assertIn("already resolved", msg.lower())

    async def test_item_revalidation_failure_aborts_before_any_write(self):
        for bad_item in (
            None,                                   # no longer owned by seller
            _item_row(is_equipped=True),            # equipped
            _item_row(locked=True),                 # locked
            _item_row(soulbound=True),              # soulbound
            _item_row(tradeable=False),             # not tradeable
            _item_row(active_listing_id=uuid4()),   # actively listed on market
        ):
            tx = _Tx(trade_row=_trade_row(gold_ask=100), item_row=bad_item)
            ok, msg, payload = await _svc(tx).accept(TRADE, BUYER)
            self.assertFalse(ok, f"accept should fail for item={bad_item}")
            self.assertIsNone(payload)
            self.assertEqual(tx.gold_fetchvals(), [])  # no gold ever deducted
            tx.execute.assert_not_awaited()            # no transfer / no flip

    async def test_zero_gold_gift_skips_deduct_but_transfers_and_flips(self):
        tx = _Tx(trade_row=_trade_row(gold_ask=0), item_row=_item_row())
        ok, msg, payload = await _svc(tx).accept(TRADE, BUYER)
        self.assertTrue(ok)
        self.assertEqual(tx.gold_fetchvals(), [])  # no gold movement either way
        self.assertTrue(any("UPDATE inventory SET character_id" in s for s in tx.executed_sql))
        self.assertIn("state='accepted'", tx.executed_sql[-1])

    async def test_wrong_recipient_cannot_accept(self):
        tx = _Tx(trade_row=_trade_row(gold_ask=100), item_row=_item_row())
        ok, msg, payload = await _svc(tx).accept(TRADE, uuid4())
        self.assertFalse(ok)
        self.assertEqual(tx.gold_fetchvals(), [])
        tx.execute.assert_not_awaited()


class TestTradeCancel(unittest.IsolatedAsyncioTestCase):
    async def test_cancel_is_conditional_on_open_state_and_sender(self):
        db = MagicMock()
        db.execute = AsyncMock(return_value="UPDATE 1")
        ok, _ = await TradeService(db).cancel(TRADE, SELLER)
        self.assertTrue(ok)
        sql = db.execute.await_args_list[0][0][0]
        self.assertIn("state='open'", sql)
        self.assertIn("from_character=$2", sql)

    async def test_cancel_losing_the_conditional_update_reports_failure(self):
        db = MagicMock()
        db.execute = AsyncMock(return_value="UPDATE 0")
        ok, _ = await TradeService(db).cancel(TRADE, SELLER)
        self.assertFalse(ok)


class TestTradeSourceInvariants(unittest.TestCase):
    """Guard the transaction/locking structure like tests/test_economy_integrity.py does."""

    @staticmethod
    def _src(rel: str) -> str:
        return (ROOT / rel).read_text()

    def test_accept_locks_trade_and_item_in_txn(self) -> None:
        src = self._src("services/trade/trade_service.py")
        self.assertIn("db.transaction()", src)
        self.assertIn("FOR UPDATE", src)
        self.assertIn("FOR UPDATE OF i", src)

    def test_item_revalidation_checks_active_market_listing(self) -> None:
        src = self._src("services/trade/trade_service.py")
        self.assertIn("ml.is_active = TRUE", src)


if __name__ == "__main__":
    unittest.main()
