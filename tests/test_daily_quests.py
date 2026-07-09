"""Regression tests for the rotating daily quest system."""

from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from services.quest.daily_quest_service import DailyQuestService


def _row(kind="kill", count=3, progress=None, is_complete=False):
    return {
        "character_id": uuid4(),
        "quest_id": "daily_slayer_3",
        "progress": dict(progress or {}),
        "is_complete": is_complete,
        "name": "Pest Control",
        "description": "Defeat 3 enemies.",
        "objectives": [{"id": "kills", "kind": kind, "description": "Defeat", "count": count}],
        "rewards": {"xp": 120, "gold": 60},
    }


def _svc(row, execute_result="UPDATE 1"):
    db = MagicMock()
    # record_event locks the row inside db.transaction(); mock the context
    # manager so `async with db.transaction() as tx` yields a tx mock.
    tx = MagicMock()
    tx.fetchrow = AsyncMock(return_value=row)
    tx.execute = AsyncMock(return_value=execute_result)
    tx_ctx = MagicMock()
    tx_ctx.__aenter__ = AsyncMock(return_value=tx)
    tx_ctx.__aexit__ = AsyncMock(return_value=False)
    db.transaction = MagicMock(return_value=tx_ctx)
    db.execute = tx.execute  # single execute mock for assertions
    svc = DailyQuestService(db)
    svc._today_row = AsyncMock(return_value=row)
    char_svc = MagicMock()
    char_svc.award_xp = AsyncMock()
    char_svc.add_gold = AsyncMock()
    return svc, db, char_svc


class TestDailyProgress(unittest.IsolatedAsyncioTestCase):
    async def test_non_matching_kind_is_ignored(self):
        svc, db, char_svc = _svc(_row(kind="explore"))
        line = await svc.record_event(char_svc, uuid4(), "kill")
        self.assertIsNone(line)
        db.execute.assert_not_awaited()

    async def test_partial_progress_updates_without_rewards(self):
        svc, db, char_svc = _svc(_row(count=3, progress={"kills": 0}))
        line = await svc.record_event(char_svc, uuid4(), "kill")
        self.assertIsNone(line)
        db.execute.assert_awaited_once()
        sql = db.execute.await_args_list[0][0][0]
        self.assertNotIn("is_complete = TRUE", sql)
        char_svc.award_xp.assert_not_awaited()
        char_svc.add_gold.assert_not_awaited()

    async def test_completion_grants_rewards_once(self):
        svc, db, char_svc = _svc(_row(count=3, progress={"kills": 2}), execute_result="UPDATE 1")
        line = await svc.record_event(char_svc, uuid4(), "kill")
        self.assertIsNotNone(line)
        self.assertIn("Pest Control", line)
        char_svc.award_xp.assert_awaited_once()
        char_svc.add_gold.assert_awaited_once()
        sql = db.execute.await_args_list[0][0][0]
        self.assertIn("is_complete = FALSE", sql)  # conditional flip guard

    async def test_losing_concurrent_completion_grants_nothing(self):
        # Another request already flipped is_complete -> UPDATE matches 0 rows.
        svc, db, char_svc = _svc(_row(count=3, progress={"kills": 2}), execute_result="UPDATE 0")
        line = await svc.record_event(char_svc, uuid4(), "kill")
        self.assertIsNone(line)
        char_svc.award_xp.assert_not_awaited()
        char_svc.add_gold.assert_not_awaited()

    async def test_already_complete_quest_is_ignored(self):
        svc, db, char_svc = _svc(_row(is_complete=True))
        line = await svc.record_event(char_svc, uuid4(), "kill")
        self.assertIsNone(line)
        db.execute.assert_not_awaited()

    async def test_progress_never_overshoots_count(self):
        svc, db, char_svc = _svc(_row(count=3, progress={"kills": 2}))
        await svc.record_event(char_svc, uuid4(), "kill", n=5)
        import json
        progress_json = db.execute.await_args_list[0][0][3]
        self.assertEqual(json.loads(progress_json), {"kills": 3})

    async def test_record_event_never_raises(self):
        svc, db, char_svc = _svc(_row())
        svc._today_row = AsyncMock(side_effect=RuntimeError("db down"))
        line = await svc.record_event(char_svc, uuid4(), "kill")
        self.assertIsNone(line)


if __name__ == "__main__":
    unittest.main()
