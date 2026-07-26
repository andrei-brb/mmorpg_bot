"""Reputation shop discount.

REPUTATION_LEVELS has advertised "5% / 10% / 15% / 20% shop discount" since it
was written and get_rep_discount() computed exactly that — but nothing called
it, so the shop charged full price at every standing. These pin the maths now
that it is wired to real gold.
"""
import unittest

from services.quest.npc_quest_service import get_rep_discount, get_rep_level


def apply_discount(base_cost: int, discount: float) -> int:
    """Mirror of _apply_discount in activity_http (kept in sync deliberately —
    a divergence here would mean players are charged something other than what
    this file claims)."""
    if discount <= 0:
        return int(base_cost)
    return max(1, int(round(int(base_cost) * (1.0 - discount))))


class TestRepDiscountTiers(unittest.TestCase):
    def test_tiers_match_the_advertised_perks(self):
        cases = [
            (-5000, 0.00),  # Hated
            (-1500, 0.00),  # Hostile
            (0, 0.00),      # Neutral
            (499, 0.00),    # just short of Friendly
            (500, 0.05),    # Friendly
            (1500, 0.10),   # Honored
            (3000, 0.15),   # Revered
            (6000, 0.20),   # Exalted
            (99999, 0.20),  # nothing beyond Exalted
        ]
        for rep, expected in cases:
            self.assertAlmostEqual(
                get_rep_discount(rep), expected, places=4,
                msg=f"rep {rep} ({get_rep_level(rep)['name']})",
            )

    def test_discount_never_makes_anything_free(self):
        # A 20% discount on a 1-gold item must still cost something; free items
        # would be an infinite-value exploit at the cheapest tier.
        for base in (1, 2, 3, 5):
            self.assertGreaterEqual(apply_discount(base, 0.20), 1)

    def test_no_standing_pays_full_price(self):
        self.assertEqual(apply_discount(1000, 0.0), 1000)

    def test_exalted_pays_eighty_percent(self):
        self.assertEqual(apply_discount(1000, 0.20), 800)
        self.assertEqual(apply_discount(2500, 0.10), 2250)

    def test_discount_is_bounded(self):
        """No standing may exceed 20% — a runaway multiplier would let a
        long-lived account buy the shop out at a rounding error."""
        for rep in range(-10000, 100001, 977):
            self.assertLessEqual(get_rep_discount(rep), 0.20)
            self.assertGreaterEqual(get_rep_discount(rep), 0.0)


if __name__ == "__main__":
    unittest.main()
