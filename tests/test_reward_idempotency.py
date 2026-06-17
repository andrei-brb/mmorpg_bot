"""Regression tests for reward-grant idempotency under concurrency (Phase 2)."""

from __future__ import annotations

import inspect
import unittest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from services.battle_pass.battle_pass_service import BattlePassService
from services.quest.npc_quest_service import NPCQuestService
from services.talents.talent_service import TalentService


class TestQuestCompletionAtomic(unittest.IsolatedAsyncioTestCase):
    """complete_quest must flip active->completed atomically; only the winning
    caller of the conditional UPDATE receives the rewards."""

    def _svc(self, update_returns):
        db = MagicMock()
        db.execute = AsyncMock()
        db.fetchrow = AsyncMock(return_value=update_returns)  # the conditional UPDATE ... RETURNING
        svc = NPCQuestService(db)
        svc.get_quest_progress = AsyncMock(return_value={"state": "active", "expires_at": None})
        svc._find_quest_template = lambda qid: {"rewards": {"gold": 10}}
        return svc, db

    async def test_winning_caller_gets_rewards(self) -> None:
        svc, db = self._svc({"quest_id": "q1"})  # UPDATE matched a row -> we won the flip
        rewards = await svc.complete_quest(uuid4(), "q1")
        self.assertEqual(rewards, {"gold": 10})
        sql = db.fetchrow.await_args_list[0][0][0]
        self.assertIn("state = 'active'", sql)  # conditional guard

    async def test_losing_caller_gets_nothing(self) -> None:
        svc, _ = self._svc(None)  # concurrent caller already flipped it -> no row, no reward
        rewards = await svc.complete_quest(uuid4(), "q1")
        self.assertIsNone(rewards)


class TestRewardIdempotencySourceInvariants(unittest.TestCase):
    def test_battle_pass_claims_before_granting(self) -> None:
        src = inspect.getsource(BattlePassService.claim_tier)
        self.assertIn("ON CONFLICT", src)
        self.assertIn("DO NOTHING", src)
        # The claim row is inserted BEFORE the reward is applied, so a duplicate
        # claim is rejected by the primary key before any grant happens.
        self.assertLess(src.index("battle_pass_claims"), src.index("apply_reward_json"))

    def test_talent_allocate_spends_points_conditionally(self) -> None:
        src = inspect.getsource(TalentService.allocate)
        self.assertIn("unspent_points >= $2", src)

    def test_talent_respec_wrapped_in_transaction(self) -> None:
        src = inspect.getsource(TalentService.respec)
        self.assertIn("db.transaction()", src)


if __name__ == "__main__":
    unittest.main()
