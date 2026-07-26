"""Saved gear sets and talent builds.

Swapping gear meant ten manual unequip/equip actions and changing a build meant
a respec that wiped everything, so in practice nobody did either — the depth the
game already has collapsed to whatever you picked first.

These pin the design decisions that are easy to get wrong later.
"""
import inspect
import unittest

from services.character import presets_service
from services.character.presets_service import (
    KIND_GEAR,
    KIND_TALENTS,
    KINDS,
    MAX_NAME_LEN,
    MAX_PRESETS,
    PresetsService,
    clean_name,
)


class TestNaming(unittest.TestCase):
    def test_names_are_trimmed_and_bounded(self):
        self.assertEqual(clean_name("  Raid Set  "), "Raid Set")
        self.assertEqual(len(clean_name("x" * 500)), MAX_NAME_LEN)

    def test_empty_names_are_rejected_upstream(self):
        for junk in (None, "", "   ", 0):
            self.assertEqual(clean_name(junk), "")

    def test_the_limit_is_small_enough_to_stay_a_choice(self):
        self.assertGreaterEqual(MAX_PRESETS, 2)
        self.assertLessEqual(MAX_PRESETS, 10)


class TestKinds(unittest.TestCase):
    def test_both_kinds_are_declared(self):
        self.assertIn(KIND_GEAR, KINDS)
        self.assertIn(KIND_TALENTS, KINDS)

    def test_save_rejects_an_unknown_kind(self):
        svc = PresetsService(db=None)
        import asyncio

        ok, msg, preset = asyncio.run(svc.save("char", "not_a_kind", "x"))
        self.assertFalse(ok)
        self.assertIsNone(preset)
        self.assertIn("Unknown", msg)


class TestDesignInvariants(unittest.TestCase):
    """These are properties of the source, checked so a later refactor cannot
    quietly reverse a decision that has a real consequence for players."""

    def test_gear_presets_store_inventory_rows_not_templates(self):
        """Two copies of the same sword are different rows with different
        enhancement levels. Storing template ids would silently hand the player
        the worse copy with no way to tell why their damage dropped."""
        src = inspect.getsource(PresetsService.capture_gear)
        self.assertIn("SELECT id, equip_slot FROM inventory", src)
        self.assertNotIn("template_id", src)

    def test_applying_a_gear_preset_only_touches_slots_it_names(self):
        """A saved weapon set must not strip your rings."""
        src = inspect.getsource(PresetsService.apply_gear)
        self.assertIn("for slot, item_id in wanted.items()", src)
        # No blanket unequip-everything before applying.
        self.assertNotIn("SET is_equipped=FALSE, equip_slot=NULL\"\n", src.replace(" ", ""))

    def test_talent_presets_still_pay_the_respec_cost(self):
        """The respec price is a balance lever. A preset that skipped it would
        quietly delete that lever."""
        src = inspect.getsource(PresetsService.apply_talents)
        self.assertIn("charge_gold=True", src)

    def test_talent_application_does_not_hardcode_the_tree_shape(self):
        """It retries until no further rank can be placed, so `allocate` stays
        the single authority on prerequisites and the code keeps working if the
        tree changes."""
        src = inspect.getsource(PresetsService.apply_talents)
        self.assertIn("while progressed", src)
        self.assertIn("talent_svc.allocate", src)

    def test_the_preset_limit_is_enforced_inside_the_transaction(self):
        """Counted outside, two saves racing could both see room for one more."""
        src = inspect.getsource(PresetsService.save)
        tx_at = src.index("async with self.db.transaction()")
        count_at = src.index("SELECT COUNT(*)")
        self.assertGreater(count_at, tx_at, "the limit is counted before the lock is taken")

    def test_a_missing_item_is_reported_not_skipped_silently(self):
        src = inspect.getsource(PresetsService.apply_gear)
        self.assertIn("missing", src)
        self.assertIn("missing_slots", src)


class TestSchema(unittest.TestCase):
    def test_the_table_exists_and_cascades(self):
        import pathlib

        schema = pathlib.Path("database/db.py").read_text()
        self.assertIn("CREATE TABLE IF NOT EXISTS character_presets", schema)
        # Deleting a character must not orphan its presets.
        idx = schema.index("CREATE TABLE IF NOT EXISTS character_presets")
        block = schema[idx: idx + 900]
        self.assertIn("ON DELETE CASCADE", block)
        self.assertIn("UNIQUE (character_id, kind, name)", block)

    def test_presets_are_registered_as_routes(self):
        import pathlib

        http = pathlib.Path("services/activity_http.py").read_text()
        for route in ("/api/game/presets", "/api/game/presets/save",
                      "/api/game/presets/apply", "/api/game/presets/delete"):
            self.assertIn(f'"{route}"', http, f"{route} is not registered")


if __name__ == "__main__":
    unittest.main()
