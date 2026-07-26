"""Enhancement cost scaling.

The cost in ENHANCEMENT_CONFIG was flat: +9 -> +10 cost 100,000 gold whether the
item was a level-5 common or a level-60 legendary. Wrong in both directions —
prohibitive early (a level-10 character never sees 100,000 gold, so the top of
the ladder does not exist for them) and trivial late (gold accumulates faster
than anything consumes it, so at 60 it is a rounding error).
"""
import inspect
import unittest

from services.blacksmith.blacksmith_service import (
    ENHANCEMENT_CONFIG,
    LEVEL_COST_SLOPE,
    RARITY_COST_MULT,
    BlacksmithService,
    enhancement_cost,
)


class TestScaling(unittest.TestCase):
    def test_a_level_one_common_still_pays_the_base_price(self):
        """The published table stays the floor, so nothing got more expensive
        for the players the old numbers were written for."""
        for step, cfg in ENHANCEMENT_CONFIG.items():
            self.assertEqual(enhancement_cost(step, 1, "common"), cfg["cost"])

    def test_higher_level_items_cost_more(self):
        cheap = enhancement_cost(5, 5, "common")
        dear = enhancement_cost(5, 60, "common")
        self.assertGreater(dear, cheap)

    def test_rarer_items_cost_more(self):
        common = enhancement_cost(5, 30, "common")
        legendary = enhancement_cost(5, 30, "legendary")
        self.assertGreater(legendary, common)

    def test_cost_still_rises_with_the_enhancement_step(self):
        costs = [enhancement_cost(s, 30, "rare") for s in sorted(ENHANCEMENT_CONFIG)]
        self.assertEqual(costs, sorted(costs))

    def test_every_rarity_in_the_table_has_a_multiplier_of_at_least_one(self):
        """A rarity multiplier below 1 would make enhancing a legendary cheaper
        than enhancing the common you are about to replace."""
        for rarity, mult in RARITY_COST_MULT.items():
            self.assertGreaterEqual(mult, 1.0, rarity)

    def test_the_slope_stays_modest(self):
        """At 0.05 a level-60 item is ~4x a level-1 one. Much steeper and low
        level gear would be the only thing anyone ever enhances."""
        self.assertGreater(LEVEL_COST_SLOPE, 0)
        self.assertLessEqual(LEVEL_COST_SLOPE, 0.1)


class TestRobustness(unittest.TestCase):
    """This sits directly in front of a gold deduction, so it must not raise."""

    def test_missing_or_junk_values_fall_back_to_the_base_cost(self):
        base = ENHANCEMENT_CONFIG[5]["cost"]
        for lvl in (None, "", "abc", 0, -3, []):
            self.assertEqual(enhancement_cost(5, lvl, "common"), base, f"level {lvl!r}")

    def test_unknown_rarity_does_not_multiply(self):
        self.assertEqual(enhancement_cost(5, 1, "shiny"), ENHANCEMENT_CONFIG[5]["cost"])
        self.assertEqual(enhancement_cost(5, 1, None), ENHANCEMENT_CONFIG[5]["cost"])

    def test_an_out_of_range_step_costs_nothing_rather_than_raising(self):
        self.assertEqual(enhancement_cost(99, 30, "epic"), 0)
        self.assertEqual(enhancement_cost(0, 30, "epic"), 0)

    def test_cost_is_never_zero_for_a_real_step(self):
        for step in ENHANCEMENT_CONFIG:
            self.assertGreaterEqual(enhancement_cost(step, 60, "artifact"), 1)


class TestQuotedPriceMatchesChargedPrice(unittest.TestCase):
    def test_both_paths_use_the_same_function(self):
        """Showing one number and charging another is the worst possible bug in
        a gold path, so both sides are checked to call the same helper."""
        charge = inspect.getsource(BlacksmithService.enhance_item)
        quote = inspect.getsource(BlacksmithService.get_enhancement_info)
        self.assertIn("enhancement_cost(", charge)
        self.assertIn("enhancement_cost(", quote)

    def test_both_queries_select_the_columns_the_formula_needs(self):
        """A missing level_req would silently price every item as level 1."""
        for fn in (BlacksmithService.enhance_item, BlacksmithService.get_enhancement_info):
            src = inspect.getsource(fn)
            self.assertIn("t.level_req", src, fn.__name__)
            self.assertIn("t.rarity", src, fn.__name__)

    def test_the_flat_table_cost_is_no_longer_charged_directly(self):
        src = inspect.getsource(BlacksmithService.enhance_item)
        self.assertNotIn('config["cost"]', src, "still charging the unscaled table cost")


if __name__ == "__main__":
    unittest.main()
