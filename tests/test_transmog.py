"""Transmog.

Gear progression forces a choice the game never let you refuse: the best item is
the one you wear, so everyone at a given level looks identical and the piece you
actually liked goes to the vendor. Character identity was decided entirely by
drop tables.
"""
import inspect
import pathlib
import re
import unittest

from services.character import transmog
from services.character.transmog import (
    TRANSMOG_CLEAR_COST,
    TRANSMOG_COST,
    TransmogService,
)


class TestPricing(unittest.TestCase):
    def test_applying_a_look_costs_gold(self):
        """Appearance is the ideal sink: purely optional, repeatable forever, and
        it competes with nothing a player needs."""
        self.assertGreater(TRANSMOG_COST, 0)

    def test_undoing_a_look_is_free(self):
        """Charging to undo a cosmetic choice punishes experimenting, which is
        the entire activity."""
        self.assertEqual(TRANSMOG_CLEAR_COST, 0)

    def test_the_cost_is_flat_not_scaled(self):
        """A level-60 player paying more to look how they want would be taxing
        the exact behaviour the feature exists to encourage."""
        src = inspect.getsource(transmog)
        self.assertNotIn("level_req *", src)
        self.assertIn("TRANSMOG_COST", inspect.getsource(TransmogService.apply))


class TestRules(unittest.TestCase):
    def test_only_the_same_slot_can_be_borrowed(self):
        """Otherwise the paperdoll stops meaning anything and a boot renders in
        a weapon frame."""
        src = inspect.getsource(TransmogService.apply)
        self.assertIn('target["equip_slot"] != source["equip_slot"]', src)

    def test_you_must_own_the_appearance(self):
        """The look is a trophy. Buying one you never earned would make the
        whole system decoration."""
        src = inspect.getsource(TransmogService.apply)
        # Both sides are resolved through the owner-scoped lookup.
        self.assertEqual(src.count("await self._row(char_id"), 2)

    def test_the_lookup_is_scoped_to_the_owner(self):
        src = inspect.getsource(TransmogService._row)
        self.assertIn("i.character_id = $2", src)

    def test_gold_and_the_change_share_one_transaction(self):
        """A failed write must never leave a player charged for an appearance
        they did not get."""
        src = inspect.getsource(TransmogService.apply)
        tx = src.index("async with self.db.transaction()")
        self.assertLess(tx, src.index("deduct_gold"))
        self.assertLess(tx, src.index("UPDATE inventory SET transmog_template_id"))

    def test_applying_the_same_look_is_refused_before_charging(self):
        src = inspect.getsource(TransmogService.apply)
        self.assertLess(
            src.index("already looks like this"),
            src.index("deduct_gold"),
            "would charge gold for a no-op",
        )


class TestItIsPurelyCosmetic(unittest.TestCase):
    """The day a stat calculation reads this column is the day a cosmetic system
    becomes a balance exploit."""

    def test_no_stat_calculation_reads_the_transmog_column(self):
        for path in (
            "services/character/character_service.py",
            "services/combat/combat_engine.py",
            "services/combat/activity_combat.py",
            "services/character/item_sets.py",
        ):
            src = pathlib.Path(path).read_text()
            self.assertNotIn("transmog", src, f"{path} reads the transmog column")

    def test_the_real_item_name_is_never_replaced(self):
        """The icon is borrowed; the NAME stays truthful, so a player can never
        be confused about what they are actually wearing."""
        src = pathlib.Path("services/character/inventory_service.py").read_text()
        self.assertIn("tm.name AS transmog_name", src)
        # The real name is still selected under its own key.
        self.assertRegex(src, r"SELECT i\.\*, t\.name,")


class TestSchema(unittest.TestCase):
    def test_the_column_exists_and_needs_no_backfill(self):
        schema = pathlib.Path("database/db.py").read_text()
        self.assertIn("ADD COLUMN IF NOT EXISTS transmog_template_id", schema)
        # NULL means "looks like itself", so every existing row is already right.
        block = schema[schema.index("transmog_template_id"):][:400]
        self.assertIn("ON DELETE SET NULL", block)
        self.assertNotIn("NOT NULL", block)

    def test_a_deleted_template_clears_the_look_rather_than_breaking_the_item(self):
        schema = pathlib.Path("database/db.py").read_text()
        block = schema[schema.index("ADD COLUMN IF NOT EXISTS transmog_template_id"):][:400]
        self.assertIn("REFERENCES item_templates(id) ON DELETE SET NULL", block)

    def test_the_endpoints_are_registered(self):
        http = pathlib.Path("services/activity_http.py").read_text()
        for route in ("/api/game/transmog/apply", "/api/game/transmog/clear",
                      "/api/game/transmog/wardrobe"):
            self.assertIn(f'"{route}"', http)


if __name__ == "__main__":
    unittest.main()
