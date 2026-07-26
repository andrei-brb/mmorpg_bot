"""Opt-in risk (oaths).

Difficulty has only ever been chosen by where you go: an enemy is as hard as its
zone and level, so once you outgear a zone every fight in it is free and there
is no way to say "make this worth my time".

These pin the two things that keep oaths honest: they pay only in XP and gold,
and a handicap the player did not accept can never be applied.
"""
import random
import unittest

from services.combat import risk
from services.combat.combat_engine import CombatEngine, CombatSession, Combatant


def _player(hp=3000):
    return Combatant(
        id="p", name="Hero", is_player=True, char_id=None,
        current_hp=hp, max_hp=hp, current_res=200, max_res=200, res_type="mana",
        attack_power=500, spell_power=500, armor=400,
        dmg_min=30, dmg_max=50, crit_chance=0.0, dodge_chance=0.0,
    )


def _enemy():
    return Combatant(
        id="e", name="Boss", is_player=False, char_id=None,
        current_hp=8000, max_hp=8000, current_res=0, max_res=0, res_type="none",
        attack_power=700, armor=300, dmg_min=60, dmg_max=60, crit_chance=0.0,
    )


class TestNormalisation(unittest.TestCase):
    def test_unknown_oaths_are_dropped_not_rejected(self):
        """An older client naming a since-renamed oath should get an ordinary
        fight, not an error it cannot recover from."""
        self.assertEqual(risk.normalize(["blind", "not_a_real_oath"]), ["blind"])

    def test_junk_input_is_survivable(self):
        for junk in (None, "", [], {}, 42, ["", None]):
            self.assertEqual(risk.normalize(junk), [])

    def test_a_single_string_is_accepted(self):
        self.assertEqual(risk.normalize("brittle"), ["brittle"])

    def test_duplicates_cannot_stack_the_same_oath(self):
        """Otherwise ["brittle"] * 10 would be a reward multiplier of 40x."""
        self.assertEqual(risk.normalize(["brittle", "brittle", "brittle"]), ["brittle"])
        self.assertEqual(risk.reward_multiplier(risk.normalize(["brittle"] * 10)),
                         risk.reward_multiplier(["brittle"]))


class TestRewards(unittest.TestCase):
    def test_no_oath_pays_exactly_normal(self):
        self.assertEqual(risk.reward_multiplier([]), 1.0)

    def test_stacking_is_worth_more_than_one(self):
        one = risk.reward_multiplier(["blind"])
        three = risk.reward_multiplier(["blind", "bare", "brittle"])
        self.assertGreater(three, one)

    def test_the_multiplier_is_capped(self):
        every = list(risk.OATHS)
        self.assertLessEqual(risk.reward_multiplier(every), risk.MAX_REWARD_MULT)

    def test_every_oath_pays_something(self):
        for key, o in risk.OATHS.items():
            self.assertGreater(o["reward_mult"], 1.0, f"{key} is a handicap with no payment")

    def test_no_oath_touches_the_loot_table(self):
        """Rewards scale XP and gold only. A handicap that improved drop rarity
        would make oaths mandatory for anyone chasing an item, and optional is
        the entire point."""
        forbidden = {"loot_rolls", "loot_mult", "rarity", "rarity_bonus", "drop_rate"}
        for key, o in risk.OATHS.items():
            self.assertFalse(
                forbidden & set(o), f"{key} declares a loot effect: {forbidden & set(o)}"
            )


class TestEffectsRequireConsent(unittest.TestCase):
    def test_nothing_applies_without_an_oath(self):
        self.assertFalse(risk.hides_intent([]))
        self.assertFalse(risk.forbids_items([]))
        self.assertFalse(risk.starts_enraged([]))
        self.assertEqual(risk.damage_taken_multiplier([]), 1.0)

    def test_each_oath_does_what_it_says(self):
        self.assertTrue(risk.hides_intent(["blind"]))
        self.assertTrue(risk.forbids_items(["bare"]))
        self.assertTrue(risk.starts_enraged(["patient"]))
        self.assertGreater(risk.damage_taken_multiplier(["brittle"]), 1.0)

    def test_an_oath_does_not_apply_another_oaths_handicap(self):
        self.assertFalse(risk.hides_intent(["bare"]))
        self.assertFalse(risk.forbids_items(["blind"]))
        self.assertEqual(risk.damage_taken_multiplier(["blind", "bare"]), 1.0)

    def test_catalog_covers_every_oath_and_quotes_its_bonus(self):
        cat = risk.catalog()
        self.assertEqual({c["id"] for c in cat}, set(risk.OATHS))
        for c in cat:
            self.assertTrue(c["name"] and c["description"])
            self.assertGreater(c["reward_bonus_pct"], 0)


class TestBrittleInCombat(unittest.TestCase):
    """Damage rolls are random, so every comparison here reseeds to the same
    value on both arms — otherwise the variance in a 30–50 damage swing is
    larger than the effect being measured."""

    @staticmethod
    def _hit(attacker_is_enemy, mult, *, pvp=False, seed=17):
        random.seed(seed)
        eng = CombatEngine()
        p = _player()
        if pvp:
            other = _player()
            other.id = "p2"
            s = CombatSession(session_id=None, players=[p, other], enemies=[])
            attacker, target = p, other
        else:
            e = _enemy()
            s = CombatSession(session_id=None, players=[p], enemies=[e], enemy_key="hogger")
            attacker, target = (e, p) if attacker_is_enemy else (p, e)
        s.player_damage_taken_mult = mult
        eng.use_ability("auto_attack", attacker, [target], session=s)
        return target.max_hp - target.current_hp

    def test_brittle_actually_increases_incoming_damage(self):
        # Summed over many seeds rather than one: a single hit can miss (95%
        # base hit chance), and a test that depends on finding a seed where it
        # did not is a test that will fail for someone else later.
        normal = sum(self._hit(True, 1.0, seed=n) for n in range(50))
        brittle = sum(
            self._hit(True, risk.damage_taken_multiplier(["brittle"]), seed=n) for n in range(50)
        )
        self.assertGreater(brittle, normal)

    def test_it_does_not_touch_the_players_own_output(self):
        self.assertEqual(self._hit(False, 2.0), self._hit(False, 1.0))

    def test_it_cannot_reach_pvp(self):
        """In a duel every hit lands on a player, so a multiplier keyed only on
        the target would double all damage in the fight."""
        self.assertEqual(self._hit(False, 2.0, pvp=True), self._hit(False, 1.0, pvp=True))


class TestSummary(unittest.TestCase):
    def test_no_oaths_reports_a_plain_fight(self):
        s = risk.summary([])
        self.assertEqual(s["oaths"], [])
        self.assertEqual(s["reward_bonus_pct"], 0)

    def test_summary_matches_the_multiplier_actually_paid(self):
        oaths = ["blind", "brittle"]
        s = risk.summary(oaths)
        expected = int(round((risk.reward_multiplier(oaths) - 1.0) * 100))
        self.assertEqual(s["reward_bonus_pct"], expected)
        self.assertEqual(len(s["oaths"]), 2)


if __name__ == "__main__":
    unittest.main()
