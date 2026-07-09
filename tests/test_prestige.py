"""Regression tests for the prestige system."""

from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from config.settings import Settings
from services.character.character_service import (
    PRESTIGE_MAX,
    PRESTIGE_XP_BONUS,
    CharacterService,
)


def _char(level=1, prestige=0, xp=0, xp_rested=0):
    return {
        "id": uuid4(),
        "class": "warrior",
        "level": level,
        "prestige": prestige,
        "xp": xp,
        "xp_rested": xp_rested,
        "current_res": 0,
        "sta": 12,
        "int_": 8,
    }


def _svc(char):
    db = MagicMock()
    db.execute = AsyncMock()
    db.fetchval = AsyncMock()
    svc = CharacterService(db)
    svc.get_by_id = AsyncMock(return_value=char)
    return svc, db


class TestPrestigeXPBonus(unittest.IsolatedAsyncioTestCase):
    async def test_award_xp_applies_prestige_multiplier(self):
        # Prestige 5 → +10% XP: 50 base becomes 55 (no level-up at level 1).
        svc, db = _svc(_char(level=1, prestige=5))
        result = await svc.award_xp(uuid4(), 50)
        self.assertEqual(result["xp_gained"], int(50 * (1 + PRESTIGE_XP_BONUS * 5)))
        self.assertEqual(result["new_level"], 1)

    async def test_award_xp_without_prestige_is_unchanged(self):
        svc, db = _svc(_char(level=1, prestige=0))
        result = await svc.award_xp(uuid4(), 50)
        self.assertEqual(result["xp_gained"], 50)

    async def test_prestige_multiplier_stacks_with_incoming_mult(self):
        # Prestige 10 → x1.2 on top of an explicit x1.5 event multiplier.
        svc, db = _svc(_char(level=1, prestige=10))
        result = await svc.award_xp(uuid4(), 40, xp_mult=1.5)
        self.assertEqual(result["xp_gained"], int(40 * (1.5 * (1.0 + PRESTIGE_XP_BONUS * 10))))


class TestPrestigeReset(unittest.IsolatedAsyncioTestCase):
    async def test_prestige_refused_below_max_level(self):
        svc, db = _svc(_char(level=Settings.MAX_LEVEL - 1, prestige=0))
        result = await svc.prestige_character(uuid4())
        self.assertEqual(result, {"ok": False, "error": "level_too_low"})
        db.fetchval.assert_not_awaited()

    async def test_prestige_refused_at_cap(self):
        svc, db = _svc(_char(level=Settings.MAX_LEVEL, prestige=PRESTIGE_MAX))
        result = await svc.prestige_character(uuid4())
        self.assertEqual(result, {"ok": False, "error": "prestige_cap"})
        db.fetchval.assert_not_awaited()

    async def test_prestige_success_resets_and_increments(self):
        svc, db = _svc(_char(level=Settings.MAX_LEVEL, prestige=2))
        db.fetchval = AsyncMock(return_value=3)
        result = await svc.prestige_character(uuid4())
        self.assertTrue(result["ok"])
        self.assertEqual(result["prestige"], 3)
        self.assertEqual(result["xp_bonus_pct"], 6)
        sql = db.fetchval.await_args[0][0]
        self.assertIn("prestige = prestige + 1", sql)
        self.assertIn("level = 1, xp = 0", sql)
        # Conditional WHERE guard makes the check-and-reset atomic.
        self.assertIn("level >= $5 AND prestige < $6", sql)
        # Cap is passed as the guard bound.
        self.assertEqual(db.fetchval.await_args[0][6], PRESTIGE_MAX)

    async def test_losing_concurrent_prestige_grants_nothing(self):
        # Guarded UPDATE matched 0 rows (another request already prestiged).
        svc, db = _svc(_char(level=Settings.MAX_LEVEL, prestige=0))
        db.fetchval = AsyncMock(return_value=None)
        result = await svc.prestige_character(uuid4())
        self.assertEqual(result, {"ok": False, "error": "not_eligible"})


if __name__ == "__main__":
    unittest.main()
