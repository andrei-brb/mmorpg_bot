"""Upgradeable idle cap.

The cap was `Settings.IDLE_REWARDS_MAX_HOURS` — one constant for every character
alive, unaffected by anything the player did. Anyone who could not open the app
daily lost the overflow permanently with no way to buy out of it, and gold had
almost nowhere to go once you were geared.
"""
import unittest

from config.settings import Settings
from services.activity_idle_rewards import compute_idle_pending, idle_pending_to_json
from services.camp_upgrades import (
    IDLE_CAP_RANKS,
    MAX_IDLE_CAP_RANK,
    base_cap_hours,
    idle_cap_hours,
    idle_cap_payload,
    next_idle_cap_rank,
)


class TestRankMaths(unittest.TestCase):
    def test_an_unupgraded_character_gets_exactly_what_it_always_did(self):
        """Existing rows default to 0 and must be untouched by this feature."""
        self.assertEqual(idle_cap_hours(0), float(Settings.IDLE_REWARDS_MAX_HOURS))
        self.assertEqual(idle_cap_hours(None), float(Settings.IDLE_REWARDS_MAX_HOURS))

    def test_each_rank_adds_hours(self):
        hours = [idle_cap_hours(r) for r in range(MAX_IDLE_CAP_RANK + 1)]
        self.assertEqual(hours, sorted(hours))
        self.assertGreater(hours[-1], hours[0])

    def test_the_cap_is_bounded(self):
        """Uncapped idle income eventually out-earns playing, and a game that
        pays better when you do not play it has stopped being a game."""
        self.assertEqual(idle_cap_hours(MAX_IDLE_CAP_RANK), idle_cap_hours(999))
        self.assertIsNone(next_idle_cap_rank(MAX_IDLE_CAP_RANK))

    def test_bad_values_mean_no_upgrade_never_an_unbounded_cap(self):
        for junk in (None, "", "abc", -5, [], {}):
            self.assertEqual(idle_cap_hours(junk), base_cap_hours(), f"{junk!r}")

    def test_each_rank_costs_more_and_is_worth_less_per_gold(self):
        """A falling rate is what gives the ladder a natural stopping point. If
        later ranks were better value, buying all of them would be automatic and
        it would stop being a decision."""
        rates = [t["extra_hours"] / t["cost"] for t in IDLE_CAP_RANKS]
        self.assertEqual(rates, sorted(rates, reverse=True), "value per gold must fall with each rank")
        costs = [t["cost"] for t in IDLE_CAP_RANKS]
        self.assertEqual(costs, sorted(costs))

    def test_ranks_are_contiguous_from_one(self):
        self.assertEqual([t["rank"] for t in IDLE_CAP_RANKS], list(range(1, MAX_IDLE_CAP_RANK + 1)))

    def test_next_rank_is_always_the_one_after_the_current(self):
        for r in range(MAX_IDLE_CAP_RANK):
            self.assertEqual(next_idle_cap_rank(r)["rank"], r + 1)


class TestPayload(unittest.TestCase):
    def test_it_quotes_the_cap_the_purchase_would_actually_give(self):
        p = idle_cap_payload(0)
        self.assertEqual(p["cap_hours"], base_cap_hours())
        self.assertEqual(p["next"]["cap_hours_after"], idle_cap_hours(1))

    def test_the_top_rank_offers_nothing_further(self):
        p = idle_cap_payload(MAX_IDLE_CAP_RANK)
        self.assertIsNone(p["next"])
        self.assertEqual(p["rank"], MAX_IDLE_CAP_RANK)


class TestAccrualUsesThePurchasedCap(unittest.TestCase):
    @staticmethod
    def _pending(rank, hours_away):
        from datetime import datetime, timedelta, timezone

        char = {
            "level": 30,
            "idle_cap_rank": rank,
            "idle_last_claim_at": datetime.now(timezone.utc) - timedelta(hours=hours_away),
        }
        return char, compute_idle_pending(char)

    def test_an_upgraded_character_banks_more(self):
        _, plain = self._pending(0, 48)
        _, upgraded = self._pending(2, 48)
        self.assertGreater(upgraded.pending_gold, plain.pending_gold)
        self.assertGreater(upgraded.pending_xp, plain.pending_xp)

    def test_time_beyond_the_cap_is_still_lost(self):
        """The upgrade raises the ceiling; it does not remove it."""
        _, at_cap = self._pending(0, float(Settings.IDLE_REWARDS_MAX_HOURS))
        _, way_over = self._pending(0, float(Settings.IDLE_REWARDS_MAX_HOURS) * 10)
        self.assertEqual(way_over.pending_gold, at_cap.pending_gold)

    def test_the_reported_cap_matches_the_one_used_to_accrue(self):
        """Reporting the global constant while accruing on the player's own cap
        would show an upgraded player 24 hours forever."""
        char, pending = self._pending(3, 10)
        payload = idle_pending_to_json(pending, char)
        self.assertEqual(payload["max_hours"], idle_cap_hours(3))
        self.assertEqual(payload["cap_upgrade"]["rank"], 3)

    def test_payload_survives_a_character_without_the_column(self):
        _, pending = self._pending(0, 5)
        payload = idle_pending_to_json(pending, {})
        self.assertEqual(payload["max_hours"], base_cap_hours())


if __name__ == "__main__":
    unittest.main()
