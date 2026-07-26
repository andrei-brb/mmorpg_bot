"""One pricing formula.

Prices came from two places that knew nothing about each other: a hardcoded
VENDOR_BUY grid with a magic `* 0.4` in database/generate_items.py, and 64
hand-written pairs in the db.py seed. Nothing enforced any relationship, so
every item added by hand was a fresh guess.

The formula in services/economy/pricing.py is fitted to the 500 live items in
migrate_add_items.sql rather than invented, so unifying the two sources does not
also reprice the game. These tests hold that line.
"""
import pathlib
import re
import statistics
import unittest

from services.economy.pricing import (
    LEVEL_GROWTH,
    RARITY_VALUE_MULT,
    SELL_RATIO,
    item_value,
    ratio_of,
    sell_price_for,
    vendor_prices,
)

_LIVE_SQL = pathlib.Path("database/migrate_add_items.sql")


def _live_items():
    """(item_type, rarity, level_req, buy, sell) for the generated item set."""
    if not _LIVE_SQL.exists():
        return []
    txt = _LIVE_SQL.read_text()
    rows = re.findall(
        r"\('[a-z]+_[a-z]+_\d+','[^']*','[^']*','(\w+)','(\w+)','[a-z_]+',(\d+),"
        r"[^)]*?,\s*(\d+),(\d+),'[^']*'\)",
        txt,
    )
    return [(r[0], r[1], int(r[2]), int(r[3]), int(r[4])) for r in rows]


class TestShape(unittest.TestCase):
    def test_price_rises_with_level_and_rarity(self):
        self.assertGreater(item_value("armor", "common", 40), item_value("armor", "common", 1))
        self.assertGreater(item_value("armor", "epic", 20), item_value("armor", "common", 20))

    def test_rarity_multipliers_only_ever_increase(self):
        order = ["common", "uncommon", "rare", "epic", "legendary", "mythic", "artifact"]
        vals = [RARITY_VALUE_MULT[r] for r in order]
        self.assertEqual(vals, sorted(vals))

    def test_growth_compounds_gently(self):
        """Linear growth makes level-60 gear feel free; steep growth makes it
        unsellable. The fitted value sits between."""
        self.assertGreater(LEVEL_GROWTH, 1.0)
        self.assertLess(LEVEL_GROWTH, 1.10)

    def test_quest_items_are_never_purchasable(self):
        self.assertEqual(item_value("quest", "legendary", 60), 0)
        self.assertEqual(vendor_prices("quest", "rare", 30), {"buy": 0, "sell": 0})


class TestSellRatio(unittest.TestCase):
    def test_one_ratio_replaces_ten(self):
        """The seed carried ten distinct sell/buy ratios (38%-50%) and the
        generator a flat 40%. The spread was accidental, not designed."""
        self.assertEqual(SELL_RATIO, 0.40)

    def test_selling_back_always_loses_you_money(self):
        """The spread is the game's oldest gold sink. A ratio at or above 1.0
        would be an infinite gold loop."""
        self.assertLess(SELL_RATIO, 1.0)
        for lvl in (1, 30, 60):
            p = vendor_prices("weapon", "epic", lvl)
            self.assertLess(p["sell"], p["buy"])

    def test_sell_price_never_rounds_to_free(self):
        for buy in (1, 2, 3):
            self.assertGreaterEqual(sell_price_for(buy), 1)

    def test_unpriced_items_stay_unpriced(self):
        self.assertEqual(sell_price_for(0), 0)
        self.assertEqual(sell_price_for(None), 0)
        self.assertIsNone(ratio_of(0, 5))
        self.assertIsNone(ratio_of(5, 0))

    def test_drops_can_be_sold_without_being_stocked(self):
        p = vendor_prices("armor", "epic", 40, sellable_only=True)
        self.assertEqual(p["buy"], 0)
        self.assertGreater(p["sell"], 0)


class TestRobustness(unittest.TestCase):
    """This feeds seed generation; it must never break a build."""

    def test_unknown_type_and_rarity_still_price(self):
        self.assertGreater(item_value("gizmo", "common", 10), 0)
        self.assertGreater(item_value("armor", "sparkly", 10), 0)

    def test_junk_levels_fall_back_to_level_one(self):
        base = item_value("armor", "common", 1)
        for junk in (None, "", "abc", 0, -5, []):
            self.assertEqual(item_value("armor", "common", junk), base, f"{junk!r}")


class TestFitsTheGameWeAlreadyHave(unittest.TestCase):
    """The formula must DESCRIBE live prices, not replace them.

    migrate_add_items.sql is applied at boot (database/db.py:1001), so these 500
    items are real. A formula that drifted from them would mean every new item
    priced itself on a different curve from every existing one — which is the
    duplication this was meant to remove, just moved.
    """

    def test_the_live_data_is_actually_there(self):
        self.assertGreater(len(_live_items()), 300, "could not parse the live item prices")

    def test_most_live_items_land_on_the_formula(self):
        items = _live_items()
        if not items:
            self.skipTest("live item SQL not available")
        errs = [item_value(t, r, lv) / buy for t, r, lv, buy, _s in items if buy > 0]
        within = sum(1 for e in errs if 0.75 <= e <= 1.30) / len(errs)
        self.assertGreater(
            within, 0.90,
            f"only {within:.0%} of live items fit the formula — it has drifted into a reprice",
        )

    def test_no_live_item_is_wildly_mispriced_by_the_formula(self):
        items = _live_items()
        if not items:
            self.skipTest("live item SQL not available")
        errs = [item_value(t, r, lv) / buy for t, r, lv, buy, _s in items if buy > 0]
        self.assertLess(max(errs), 2.0, "formula more than doubles a live price")
        self.assertGreater(min(errs), 0.5, "formula more than halves a live price")

    def test_the_live_sell_ratio_matches_the_constant(self):
        items = _live_items()
        if not items:
            self.skipTest("live item SQL not available")
        ratios = [s / b for _t, _r, _lv, b, s in items if b and s]
        self.assertAlmostEqual(statistics.median(ratios), SELL_RATIO, places=2)


class TestSingleSourceOfTruth(unittest.TestCase):
    def test_the_generator_no_longer_carries_its_own_price_table(self):
        src = pathlib.Path("database/generate_items.py").read_text()
        self.assertIn("from services.economy.pricing import vendor_prices", src)
        self.assertIn("vendor_prices(", src)
        # The old grid may linger as a retired record, and the docstring may
        # still describe what was removed — so check the executable lines only.
        code = "\n".join(
            ln for ln in src.splitlines()
            if ln.strip() and not ln.lstrip().startswith("#")
        )
        self.assertNotIn("VENDOR_BUY[rarity][index]", code)
        self.assertNotIn("vendor_buy_price * 0.4", code)



class TestMarketBounds(unittest.TestCase):
    """The market accepted any price above zero, which allowed a listing below
    what a vendor already pays (strictly worse than not listing it, so only ever
    a mistake) and a Health Potion for 999,999,999 gold (nobody buys it, but it
    tops a price-sorted page and anchors what people think things are worth)."""

    def test_a_listing_can_never_undercut_the_vendor(self):
        from services.economy.pricing import check_market_price, market_price_bounds

        b = market_price_bounds("weapon", "legendary", 60)
        ok, msg, _ = check_market_price(b["min"] - 1, "weapon", "legendary", 60)
        self.assertFalse(ok)
        self.assertIn("vendor", msg.lower())

    def test_absurd_prices_are_refused(self):
        from services.economy.pricing import check_market_price

        ok, msg, _ = check_market_price(10**9, "consumable", "common", 1)
        self.assertFalse(ok)
        self.assertIn("most this can be listed", msg)

    def test_the_message_names_the_price_that_would_work(self):
        """A rejection that does not say what would be accepted costs the player
        another round trip to find out."""
        from services.economy.pricing import check_market_price, market_price_bounds

        b = market_price_bounds("armor", "epic", 40)
        _ok, low_msg, _ = check_market_price(1, "armor", "epic", 40)
        _ok2, high_msg, _ = check_market_price(10**9, "armor", "epic", 40)
        self.assertIn(f"{b['min']:,}", low_msg)
        self.assertIn(f"{b['max']:,}", high_msg)

    def test_honest_prices_are_accepted(self):
        from services.economy.pricing import check_market_price, market_price_bounds

        for args in (("weapon", "rare", 30), ("armor", "epic", 45), ("material", "common", 1)):
            b = market_price_bounds(*args)
            for p in (b["min"], (b["min"] + b["max"]) // 2, b["max"]):
                ok, msg, _ = check_market_price(p, *args)
                self.assertTrue(ok, f"{args} at {p}: {msg}")

    def test_the_ceiling_leaves_room_for_a_genuinely_great_item(self):
        """+10 enhancement alone doubles an item's stats and rolled stats stack
        on top. A tight ceiling would block real trades to prevent fake ones."""
        from services.economy.pricing import MARKET_CEILING_MULT

        self.assertGreaterEqual(MARKET_CEILING_MULT, 100)

    def test_the_stored_vendor_price_wins_over_the_formula(self):
        """The floor must match what a vendor will actually pay today, not what
        the formula thinks it should be."""
        from services.economy.pricing import SELL_RATIO, market_price_bounds

        b = market_price_bounds("weapon", "common", 1, vendor_buy=10_000)
        self.assertEqual(b["min"], int(round(10_000 * SELL_RATIO)))

    def test_unpriced_items_are_still_listable(self):
        from services.economy.pricing import market_price_bounds

        b = market_price_bounds("quest", "rare", 30)
        self.assertEqual(b["min"], 1)
        self.assertGreater(b["max"], 1)

    def test_junk_prices_are_refused_not_crashed_on(self):
        from services.economy.pricing import check_market_price

        for junk in (None, "", "abc", [], {}):
            ok, _msg, _b = check_market_price(junk, "weapon", "rare", 20)
            self.assertFalse(ok, f"{junk!r}")

    def test_the_market_endpoint_enforces_it(self):
        http = pathlib.Path("services/activity_http.py").read_text()
        self.assertIn("check_market_price(", http)
        self.assertIn("price_out_of_bounds", http)


if __name__ == "__main__":
    unittest.main()
