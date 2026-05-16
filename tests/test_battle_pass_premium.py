"""Battle pass premium track claim."""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from services.battle_pass.battle_pass_service import BattlePassService


def _season_row():
    now = datetime.now(timezone.utc)
    return {
        "id": 1,
        "key": "season_1",
        "name": "Season I",
        "starts_at": now - timedelta(days=1),
        "ends_at": now + timedelta(days=27),
        "max_tier": 50,
        "xp_per_tier": 100,
        "weekend_multiplier": 2.0,
        "is_active": True,
    }


class TestBattlePassPremiumClaim(unittest.IsolatedAsyncioTestCase):
    async def test_claim_premium_blocked_when_locked(self):
        char_id = uuid4()
        db = MagicMock()
        db.fetchrow = AsyncMock(
            side_effect=[
                _season_row(),
                {"character_id": char_id, "season_id": 1, "xp": 500, "premium_unlocked_at": None},
            ]
        )
        db.fetchval = AsyncMock(return_value=False)
        db.execute = AsyncMock()

        bp = BattlePassService(db)
        with patch.object(bp, "ensure_active_season", AsyncMock(return_value=_season_row())):
            with patch.object(bp, "_get_or_create_progress", AsyncMock(return_value={"xp": 500})):
                with patch.object(bp, "_premium_unlocked", AsyncMock(return_value=False)):
                    ok, msg, delivery = await bp.claim_tier(char_id, 1, "premium")

        self.assertFalse(ok)
        self.assertIn("locked", msg.lower())
        self.assertIsNone(delivery)

    def test_premium_tier_rows_respect_unlock_flag(self):
        bp = BattlePassService(MagicMock())
        rows = bp._build_tier_rows(
            [{"tier": 1, "reward": {"gold": 50}}],
            "premium",
            current_tier=5,
            claimed_set=set(),
            premium_ok=False,
        )
        self.assertTrue(rows[0]["locked_premium"])
        self.assertFalse(rows[0]["claimable"])

        unlocked = bp._build_tier_rows(
            [{"tier": 1, "reward": {"gold": 50}}],
            "premium",
            current_tier=5,
            claimed_set=set(),
            premium_ok=True,
        )
        self.assertFalse(unlocked[0]["locked_premium"])
        self.assertTrue(unlocked[0]["claimable"])

    def test_default_premium_rewards_seeded_for_all_tiers(self):
        rewards = BattlePassService._default_premium_tier_rewards()
        self.assertGreaterEqual(len(rewards), 30)
        self.assertIn("gold", rewards[1])


if __name__ == "__main__":
    unittest.main()
