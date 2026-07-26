"""Directed expeditions.

Exploring was a button that rolled fixed odds — 40% enemy, 15% boss, 20% loot —
identical for every player, in every zone, on every press, with no decision
changing them. "Explore" meant "press again": a slot machine where the player
waits rather than plays.
"""
import inspect
import unittest

from services.exploration import expeditions, zone_explore
from services.exploration.expeditions import (
    DEFAULT_FOCUS,
    FOCUSES,
    MIN_BAND,
    apply_to_bands,
    catalog,
    normalize,
)

BASE = {"enemy": 0.40, "boss": 0.15, "loot": 0.20}


class TestNormalisation(unittest.TestCase):
    def test_unknown_focuses_fall_back(self):
        for junk in (None, "", "nonsense", 7, [], "; DROP"):
            self.assertIn(normalize(junk), FOCUSES)
        self.assertEqual(normalize("nonsense"), DEFAULT_FOCUS)

    def test_known_focuses_survive(self):
        for key in FOCUSES:
            self.assertEqual(normalize(key), key)
            self.assertEqual(normalize(key.upper()), key)


class TestDistributionIsAlwaysValid(unittest.TestCase):
    """Bands are cumulative over one random draw, so an invalid distribution
    would not error — it would silently truncate the last outcome."""

    def test_every_focus_sums_to_one(self):
        for key in FOCUSES:
            shares = apply_to_bands(key, **BASE)
            self.assertAlmostEqual(sum(shares.values()), 1.0, places=6, msg=key)

    def test_no_outcome_is_ever_eliminated(self):
        """A focus expresses a preference. An outcome at 0% would make it a
        promise, and a player hunting for an hour should still occasionally
        stumble on something."""
        for key in FOCUSES:
            for name, share in apply_to_bands(key, **BASE).items():
                self.assertGreater(share, 0.0, f"{key} eliminated {name}")

    def test_targeted_outcomes_keep_a_floor(self):
        for key in FOCUSES:
            shares = apply_to_bands(key, **BASE)
            for name in ("enemy", "boss", "loot"):
                self.assertGreaterEqual(shares[name], MIN_BAND - 1e-9, f"{key}/{name}")

    def test_it_survives_extreme_inputs(self):
        """boss_chance_add from live events widens the boss band; the focus must
        not turn that into an invalid distribution."""
        for key in FOCUSES:
            for extreme in ({"enemy": 0.9, "boss": 0.9, "loot": 0.9},
                            {"enemy": 0.0, "boss": 0.0, "loot": 0.0},
                            {"enemy": 0.55, "boss": 0.30, "loot": 0.35}):
                shares = apply_to_bands(key, **extreme)
                self.assertAlmostEqual(sum(shares.values()), 1.0, places=6, msg=f"{key} {extreme}")
                for name, share in shares.items():
                    self.assertGreaterEqual(share, 0.0, f"{key}/{name} {extreme}")


class TestFocusesRedistributeRatherThanImprove(unittest.TestCase):
    def test_wander_is_exactly_the_historical_roll(self):
        """An unfocused explore must be bit-for-bit the roll this has always
        been, or this feature silently rebalances exploration for everyone."""
        shares = apply_to_bands("wander", **BASE)
        self.assertAlmostEqual(shares["enemy"], 0.40, places=6)
        self.assertAlmostEqual(shares["boss"], 0.15, places=6)
        self.assertAlmostEqual(shares["loot"], 0.20, places=6)
        self.assertAlmostEqual(shares["safe"], 0.25, places=6)

    def test_every_focus_gives_something_up(self):
        """Nothing may raise all three rewarding outcomes at once — that would
        be a strict upgrade over wandering and make wandering pointless."""
        for key, f in FOCUSES.items():
            if key == DEFAULT_FOCUS:
                continue
            deltas = [f["enemy"], f["boss"], f["loot"]]
            self.assertTrue(any(d < 0 for d in deltas), f"{key} costs nothing")
            self.assertTrue(any(d > 0 for d in deltas), f"{key} gains nothing")

    def test_each_focus_actually_favours_what_it_claims(self):
        base = apply_to_bands("wander", **BASE)
        self.assertGreater(apply_to_bands("hunt", **BASE)["enemy"], base["enemy"])
        self.assertGreater(apply_to_bands("stalk", **BASE)["boss"], base["boss"])
        self.assertGreater(apply_to_bands("scavenge", **BASE)["loot"], base["loot"])

    def test_scavenging_really_does_cost_you_fights(self):
        base = apply_to_bands("wander", **BASE)
        scav = apply_to_bands("scavenge", **BASE)
        self.assertLess(scav["enemy"], base["enemy"])


class TestWiring(unittest.TestCase):
    def test_the_roller_accepts_a_focus(self):
        sig = inspect.signature(zone_explore.roll_explore_outcome)
        self.assertIn("focus", sig.parameters)
        self.assertEqual(sig.parameters["focus"].default, "wander")

    def test_the_roller_no_longer_uses_hardcoded_boundaries(self):
        src = inspect.getsource(zone_explore.roll_explore_outcome)
        self.assertNotIn("0.75 + add", src, "still using the fixed loot boundary")
        self.assertIn("apply_to_bands", src)

    def test_catalog_covers_every_focus_and_explains_the_trade(self):
        cat = catalog()
        self.assertEqual({c["id"] for c in cat}, set(FOCUSES))
        for c in cat:
            self.assertTrue(c["name"] and c["description"])
            self.assertIn("shifts", c)

    def test_the_endpoints_are_wired(self):
        import pathlib

        http = pathlib.Path("services/activity_http.py").read_text()
        self.assertIn('"/api/game/explore/focuses"', http)
        self.assertIn("expeditions.normalize(", http)
        self.assertIn("focus=focus", http)


if __name__ == "__main__":
    unittest.main()
