"""Guild tech bank cap and fund requirements."""

from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from services.guild import guild_tech as guild_tech_mod


class TestGuildTechHelpers(unittest.IsolatedAsyncioTestCase):
    async def test_bank_withdraw_cap_default(self):
        db = MagicMock()
        db.fetch = AsyncMock(return_value=[])
        cap = await guild_tech_mod.bank_withdraw_cap(db, uuid4())
        self.assertEqual(cap, guild_tech_mod.DEFAULT_BANK_WITHDRAW_CAP)

    async def test_bank_withdraw_cap_with_treasury(self):
        db = MagicMock()
        db.fetch = AsyncMock(return_value=[{"node_id": "guild_treasury_1"}])
        cap = await guild_tech_mod.bank_withdraw_cap(db, uuid4())
        self.assertGreater(cap, guild_tech_mod.DEFAULT_BANK_WITHDRAW_CAP)

    async def test_can_unlock_blocks_without_fund(self):
        guild_id = uuid4()
        db = MagicMock()
        db.fetch = AsyncMock(return_value=[])
        db.fetchval = AsyncMock(return_value=0)
        db.fetchrow = AsyncMock(return_value={"guild_xp": 9999, "bank_gold": 9999})
        ok, msg = await guild_tech_mod.can_unlock(db, guild_id, "guild_bounty_1")
        self.assertFalse(ok)
        self.assertIn("fund", msg.lower())


if __name__ == "__main__":
    unittest.main()
