"""Unit tests for guild invite persistence helpers."""

from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from services.guild import guild_invites as gi


class TestGuildInvites(unittest.IsolatedAsyncioTestCase):
    async def test_get_valid_pending_invite_queries(self) -> None:
        db = MagicMock()
        gid = uuid4()
        db.fetchrow = AsyncMock(return_value={"id": uuid4()})
        row = await gi.get_valid_pending_invite(db, gid, 12345)
        self.assertIsNotNone(row)
        sql = db.fetchrow.call_args[0][0]
        self.assertIn("status='pending'", sql)
        self.assertIn("expires_at > NOW()", sql)

    async def test_upsert_expires_old_pending(self) -> None:
        db = MagicMock()
        db.execute = AsyncMock()
        gid = uuid4()
        await gi.upsert_pending_invite(db, gid, 99, inviter_character_id=uuid4())
        self.assertEqual(db.execute.await_count, 2)
        first_sql = db.execute.await_args_list[0][0][0]
        self.assertIn("status='expired'", first_sql)


if __name__ == "__main__":
    unittest.main()
