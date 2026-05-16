"""Guild raid strike auto-settle and tech fund unlock."""

from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from services.guild import guild_raid as guild_raid_mod
from services.guild import guild_tech as guild_tech_mod


class TestGuildRaidStrike(unittest.IsolatedAsyncioTestCase):
    async def test_strike_reduces_hp_and_auto_settles_at_zero(self):
        run_id = uuid4()
        guild_id = uuid4()
        char_id = uuid4()
        char = {"id": char_id, "guild_id": guild_id, "level": 10, "class": "warrior"}

        run_row = {
            "id": run_id,
            "guild_id": guild_id,
            "status": "active",
            "template_key": "gnoll_warren_raid",
            "boss_hp_remaining": 50,
            "boss_hp_max": 25_000,
        }
        run_cleared = {**run_row, "boss_hp_remaining": 0, "status": "completed"}

        db = MagicMock()
        db.fetchrow = AsyncMock(side_effect=[run_row, run_cleared, run_cleared])
        db.execute = AsyncMock()
        db.fetchval = AsyncMock(return_value=0)
        db.fetch = AsyncMock(return_value=[{"character_id": char_id}])

        char_svc = MagicMock()
        char_svc.on_cooldown = AsyncMock(return_value=0)
        char_svc.set_cooldown = AsyncMock()
        char_svc.add_gold = AsyncMock()

        with patch.object(guild_raid_mod, "_strike_damage", AsyncMock(return_value=50)):
            with patch.object(guild_raid_mod, "_is_signed_up", AsyncMock(return_value=True)):
                with patch.object(guild_raid_mod, "settle_run", AsyncMock(return_value=(True, ""))) as settle:
                    ok, msg, _ = await guild_raid_mod.strike(db, char_svc, run_id, char)

        self.assertTrue(ok)
        self.assertIn("cleared", msg.lower())
        settle.assert_awaited_once()


class TestGuildTechContribute(unittest.IsolatedAsyncioTestCase):
    async def test_contribute_records_gold(self):
        guild_id = uuid4()
        char_id = uuid4()
        node_id = "guild_bounty_1"

        db = MagicMock()
        db.fetch = AsyncMock(return_value=[])
        db.execute = AsyncMock()
        db.fetchval = AsyncMock(return_value=100)

        char_svc = MagicMock()
        char_svc.deduct_gold = AsyncMock(return_value=True)

        ok, msg, progress = await guild_tech_mod.contribute(db, char_svc, guild_id, node_id, char_id, 50)
        self.assertTrue(ok)
        self.assertIn("50", msg)
        self.assertIsNotNone(progress)
        char_svc.deduct_gold.assert_awaited_once()
        db.execute.assert_awaited()


if __name__ == "__main__":
    unittest.main()
