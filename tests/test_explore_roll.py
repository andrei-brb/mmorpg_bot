"""Unit tests for explore outcome rolls (zone patrol + lore world boss windows)."""

from __future__ import annotations

import random
import unittest
from unittest.mock import patch

from config.settings import ZONES
from services.exploration.zone_explore import roll_explore_outcome


class TestRollExploreOutcome(unittest.TestCase):
    def setUp(self) -> None:
        self.zone = ZONES["elwynn_forest"]

    def test_patrol_dead_without_lore_never_returns_boss(self) -> None:
        for seed in range(80):
            random.seed(seed)
            for _ in range(30):
                out = roll_explore_outcome(
                    self.zone,
                    0.0,
                    zone_patrol_boss_alive=False,
                    world_boss_key=None,
                )
                self.assertNotEqual(out["type"], "boss", msg=f"seed={seed} out={out}")

    def test_lore_window_boss_when_patrol_dead(self) -> None:
        with patch("random.random", return_value=0.42):
            out = roll_explore_outcome(
                self.zone,
                0.0,
                zone_patrol_boss_alive=False,
                world_boss_key="hogger",
            )
        self.assertEqual(out["type"], "boss")
        self.assertEqual(out["key"], "hogger")

    def test_patrol_alive_uses_zone_boss_pool_without_window(self) -> None:
        with patch("random.random", return_value=0.42):
            out = roll_explore_outcome(
                self.zone,
                0.0,
                zone_patrol_boss_alive=True,
                world_boss_key=None,
            )
        self.assertEqual(out["type"], "boss")
        self.assertIn(out["key"], self.zone.bosses)

    def test_window_overrides_boss_key_when_patrol_alive(self) -> None:
        with patch("random.random", return_value=0.42):
            out = roll_explore_outcome(
                self.zone,
                0.0,
                zone_patrol_boss_alive=True,
                world_boss_key="hogger",
            )
        self.assertEqual(out["type"], "boss")
        self.assertEqual(out["key"], "hogger")


if __name__ == "__main__":
    unittest.main()
