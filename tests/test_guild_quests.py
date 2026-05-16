"""Guild hall quest board progress and claims."""

from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from services.guild import guild_quests as gq


class TestGuildQuestRecordEvent(unittest.IsolatedAsyncioTestCase):
    async def test_record_event_completes_daily_checkin_quest(self):
        guild_id = uuid4()
        db = MagicMock()
        db.fetchrow = AsyncMock(return_value=None)
        db.execute = AsyncMock()

        await gq.record_event(db, guild_id, "checkin", 1)

        self.assertGreaterEqual(db.execute.await_count, 1)
        sql = db.execute.await_args_list[-1][0][0]
        self.assertIn("guild_quest_progress", sql)

    async def test_record_event_increments_partial_progress(self):
        guild_id = uuid4()
        db = MagicMock()
        db.fetchrow = AsyncMock(return_value={"current_value": 1, "completed_at": None})
        db.execute = AsyncMock()

        await gq.record_event(db, guild_id, "raid_strike", 1)

        db.execute.assert_awaited()
        args = db.execute.await_args[0]
        self.assertIn("guild_quest_progress", args[0])


class TestGuildQuestClaim(unittest.IsolatedAsyncioTestCase):
    async def test_claim_unknown_quest_fails(self):
        db = MagicMock()
        char_svc = MagicMock()
        ok, msg, delivery, quests = await gq.claim(db, char_svc, uuid4(), uuid4(), "not_a_quest")
        self.assertFalse(ok)
        self.assertIn("Unknown", msg)
        self.assertIsNone(delivery)

    async def test_claim_before_complete_fails(self):
        guild_id = uuid4()
        char_id = uuid4()
        db = MagicMock()
        db.fetchrow = AsyncMock(side_effect=[{"current_value": 0, "completed_at": None}, None])
        char_svc = MagicMock()

        ok, msg, _, _ = await gq.claim(db, char_svc, guild_id, char_id, "daily_hall_muster")
        self.assertFalse(ok)
        self.assertIn("not complete", msg.lower())


if __name__ == "__main__":
    unittest.main()
