"""Unit tests for guild invite persistence helpers."""

from __future__ import annotations

import unittest
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from services.guild import guild_invites as gi


def _txn_db(conn):
    """A fake db whose .transaction() yields `conn` (mirrors Database.transaction())."""
    db = MagicMock()

    @asynccontextmanager
    async def _txn():
        yield conn

    db.transaction = _txn
    return db


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

    async def test_upsert_expires_old_pending_atomically(self) -> None:
        # Expire + insert must run on the SAME transaction connection (atomic),
        # in the order expire-then-insert.
        conn = MagicMock()
        conn.execute = AsyncMock()
        db = _txn_db(conn)
        gid = uuid4()
        await gi.upsert_pending_invite(db, gid, 99, inviter_character_id=uuid4())
        self.assertEqual(conn.execute.await_count, 2)
        first_sql = conn.execute.await_args_list[0][0][0]
        self.assertIn("status='expired'", first_sql)
        second_sql = conn.execute.await_args_list[1][0][0]
        self.assertIn("INSERT INTO guild_invites", second_sql)


if __name__ == "__main__":
    unittest.main()
