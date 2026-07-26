"""Combat consumables.

Before this, the only thing usable in a fight was one healing potion, found by a
query hardcoded to `effect_type = 'heal_hp'`. Every other consumable the game
sells is a ten-minute out-of-combat stat buff — a shopping decision, not a
combat one.

These pin the two properties that make the new items safe: they never cost you
an item for nothing, and their magnitudes scale with the character instead of
ageing out the way the potion's flat "80" did.
"""
import unittest

from services.combat.combat_engine import Combatant, StatusEffect
from services.combat.consumables import (
    COMBAT_EFFECTS,
    CURABLE,
    MAX_ITEMS_PER_FIGHT,
    THROWN_DAMAGE_AP_SHARE,
    apply_combat_consumable,
    is_combat_usable,
)


def _player(hp=2000, res=200, ap=500):
    return Combatant(
        id="p", name="Hero", is_player=True, char_id=None,
        current_hp=hp, max_hp=hp, current_res=res, max_res=res, res_type="mana",
        attack_power=ap, spell_power=ap, armor=300,
        dmg_min=20, dmg_max=40, crit_chance=0.0,
    )


def _enemy(hp=5000):
    return Combatant(
        id="e", name="Boss", is_player=False, char_id=None,
        current_hp=hp, max_hp=hp, current_res=0, max_res=0, res_type="none",
        attack_power=600, armor=400, dmg_min=40, dmg_max=70, crit_chance=0.0,
    )


class TestNeverWasteAnItem(unittest.TestCase):
    """Every one of these returns False, and the caller only spends the item
    when it gets True. Getting that backwards is how players lose things to a
    misclick."""

    def test_antidote_with_nothing_to_cure(self):
        p = _player()
        changed, msg = apply_combat_consumable("combat_cure", 0, "Antidote", p, _enemy())
        self.assertFalse(changed)
        self.assertIn("Antidote", msg)

    def test_draught_at_full_resource(self):
        p = _player()
        changed, _ = apply_combat_consumable("combat_restore", 40, "Focus Draught", p, _enemy())
        self.assertFalse(changed)

    def test_draught_on_a_class_with_no_resource(self):
        p = _player()
        p.max_res = p.current_res = 0
        p.res_type = "none"
        changed, _ = apply_combat_consumable("combat_restore", 40, "Focus Draught", p, _enemy())
        self.assertFalse(changed)

    def test_potion_at_full_health(self):
        p = _player()
        changed, _ = apply_combat_consumable("heal_hp", 80, "Health Potion", p, _enemy())
        self.assertFalse(changed)

    def test_thrown_item_with_no_target(self):
        p = _player()
        changed, _ = apply_combat_consumable("combat_damage", 0, "Alchemist's Fire", p, None)
        self.assertFalse(changed)

        dead = _enemy()
        dead.is_dead = True
        changed, _ = apply_combat_consumable("combat_damage", 0, "Alchemist's Fire", p, dead)
        self.assertFalse(changed)


class TestEffectsScaleWithTheCharacter(unittest.TestCase):
    def test_healing_ignores_the_stale_flat_value_when_the_character_outgrew_it(self):
        """The potion's stored value is 80, written for level-5 content. At 2000
        max HP that is noise, so the flat number is a floor, not the answer."""
        small, big = _player(hp=200), _player(hp=20_000)
        small.current_hp, big.current_hp = 1, 1
        apply_combat_consumable("heal_hp", 80, "Health Potion", small, _enemy())
        apply_combat_consumable("heal_hp", 80, "Health Potion", big, _enemy())
        self.assertGreater(big.current_hp, small.current_hp * 10)

    def test_shield_scales_with_max_health(self):
        small, big = _player(hp=200), _player(hp=20_000)
        apply_combat_consumable("combat_shield", 35, "Warding Stone", small, _enemy())
        apply_combat_consumable("combat_shield", 35, "Warding Stone", big, _enemy())
        self.assertEqual(small.get_status(StatusEffect.SHIELD).value, 70)
        self.assertEqual(big.get_status(StatusEffect.SHIELD).value, 7000)

    def test_restore_is_a_percentage_of_the_pool(self):
        p = _player(res=1000)
        p.current_res = 0
        apply_combat_consumable("combat_restore", 40, "Focus Draught", p, _enemy())
        self.assertEqual(p.current_res, 400)

    def test_thrown_damage_scales_with_attack_power(self):
        weak, strong = _player(ap=100), _player(ap=2000)
        e1, e2 = _enemy(), _enemy()
        apply_combat_consumable("combat_damage", 0, "Alchemist's Fire", weak, e1)
        apply_combat_consumable("combat_damage", 0, "Alchemist's Fire", strong, e2)
        self.assertGreater(e1.max_hp - e1.current_hp, 0)
        self.assertGreater((e2.max_hp - e2.current_hp), (e1.max_hp - e1.current_hp) * 10)


class TestCureIsNotACatchAll(unittest.TestCase):
    def test_it_clears_every_damage_over_time(self):
        p = _player()
        for eff in CURABLE:
            p.add_status(eff, 20, 3, "boss")
        changed, _ = apply_combat_consumable("combat_cure", 0, "Antidote", p, _enemy())
        self.assertTrue(changed)
        for eff in CURABLE:
            self.assertFalse(p.has(eff), f"{eff.value} survived the antidote")

    def test_it_does_not_break_crowd_control(self):
        """A cure that also cleared stun and slow would collapse three separate
        counters into one item."""
        p = _player()
        p.add_status(StatusEffect.POISON, 20, 3, "boss")
        p.add_status(StatusEffect.STUN, 0, 1, "boss")
        p.add_status(StatusEffect.SLOW, 30, 2, "boss")
        apply_combat_consumable("combat_cure", 0, "Antidote", p, _enemy())
        self.assertTrue(p.has(StatusEffect.STUN))
        self.assertTrue(p.has(StatusEffect.SLOW))
        self.assertFalse(p.has(StatusEffect.POISON))


class TestBounds(unittest.TestCase):
    def test_thrown_damage_stays_in_the_band_of_one_ability(self):
        """It lands unmitigated AND does not cost your turn. Free and
        unmitigated is a dangerous pair, so the share must stay small — a first
        pass at 0.55 was worth roughly six auto-attacks, three times a fight."""
        self.assertLessEqual(THROWN_DAMAGE_AP_SHARE, 0.25)

    def test_the_per_fight_budget_is_small(self):
        self.assertGreaterEqual(MAX_ITEMS_PER_FIGHT, 1)
        self.assertLessEqual(MAX_ITEMS_PER_FIGHT, 5)

    def test_only_known_effects_are_usable_in_combat(self):
        for eff in COMBAT_EFFECTS:
            self.assertTrue(is_combat_usable(eff))
        for eff in ("boost_sta", "boost_resistance", "", None, "nonsense"):
            self.assertFalse(is_combat_usable(eff), f"{eff!r} should not work mid-fight")

    def test_an_out_of_combat_buff_is_refused_rather_than_silently_ignored(self):
        p = _player()
        changed, msg = apply_combat_consumable("boost_sta", 5, "Stamina Draught", p, _enemy())
        self.assertFalse(changed)
        self.assertIn("Stamina Draught", msg)

    def test_a_lethal_throw_marks_the_enemy_dead(self):
        p = _player(ap=5000)
        e = _enemy(hp=10)
        changed, _ = apply_combat_consumable("combat_damage", 0, "Alchemist's Fire", p, e)
        self.assertTrue(changed)
        self.assertEqual(e.current_hp, 0)
        self.assertTrue(e.is_dead, "killed by an item but never marked dead")


class TestSeededItemsExist(unittest.TestCase):
    def test_every_combat_effect_has_an_item_that_grants_it(self):
        """A consumable effect the game never sells is dead code."""
        import pathlib

        seed = pathlib.Path("database/db.py").read_text()
        for eff in COMBAT_EFFECTS:
            self.assertIn(f"'{eff}'", seed, f"no item template grants {eff}")


if __name__ == "__main__":
    unittest.main()
