"""Unit tests for world event reward multipliers."""

from __future__ import annotations

import json
import unittest
from unittest.mock import AsyncMock, MagicMock

from services.reward_multipliers import (
    _parse_world_event_multipliers,
    get_combined_reward_multipliers,
)


class TestParseWorldEventMultipliers(unittest.TestCase):
    def test_dict_multipliers(self) -> None:
        xp, gold = _parse_world_event_multipliers(
            {"xp_multiplier": 1.5, "gold_multiplier": 1.25}
        )
        self.assertEqual(xp, 1.5)
        self.assertEqual(gold, 1.25)

    def test_json_string(self) -> None:
        xp, gold = _parse_world_event_multipliers(
            json.dumps({"xp_multiplier": 2.0, "gold_multiplier": 1.0})
        )
        self.assertEqual(xp, 2.0)
        self.assertEqual(gold, 1.0)

    def test_missing_defaults_to_one(self) -> None:
        xp, gold = _parse_world_event_multipliers(None)
        self.assertEqual(xp, 1.0)
        self.assertEqual(gold, 1.0)


class TestCombinedRewardMultipliers(unittest.IsolatedAsyncioTestCase):
    async def test_applies_active_world_event(self) -> None:
        db = MagicMock()
        db.fetchrow = AsyncMock(
            return_value={"state": {"xp_multiplier": 1.5, "gold_multiplier": 1.25}},
        )
        xp, gold, boss = await get_combined_reward_multipliers(db, None)
        self.assertEqual(xp, 1.5)
        self.assertEqual(gold, 1.25)
        self.assertEqual(boss, 0.0)


if __name__ == "__main__":
    unittest.main()
