"""Elemental matchups and boss phases.

Both exist to make a turn a decision. Matchups mean "which ability" has a
different answer in different fights; phases mean a boss you have nearly killed
is a different opponent from the one you opened on.
"""
import random
import unittest

from config.settings import ENEMIES
from services.combat.combat_engine import (
    ABILITIES,
    PHASE_ANNOUNCE,
    PHASE_LABEL,
    PHASE_THRESHOLDS,
    SIGNATURE_RATE_BY_PHASE,
    CombatEngine,
    CombatSession,
    Combatant,
)
from services.combat.elements import (
    BEATEN_BY,
    BEATS,
    PHYSICAL,
    STRONG_MULT,
    WEAK_MULT,
    ability_element,
    effectiveness,
    enemy_element,
    enemy_element_payload,
    matchup,
)


def _enemy(hp=4000, ap=800, armor=200):
    return Combatant(
        id="e", name="Boss", is_player=False, char_id=None,
        current_hp=hp, max_hp=hp, current_res=0, max_res=0, res_type="none",
        attack_power=ap, spell_power=ap, armor=armor,
        dmg_min=40, dmg_max=80, crit_chance=0.0,
    )


def _player(hp=3000):
    return Combatant(
        id="p", name="Hero", is_player=True, char_id=None,
        current_hp=hp, max_hp=hp, current_res=500, max_res=500, res_type="mana",
        attack_power=600, spell_power=600, armor=400,
        dmg_min=40, dmg_max=60, crit_chance=0.0, dodge_chance=0.0,
    )


class TestMatchupTable(unittest.TestCase):
    def test_the_ring_has_no_globally_correct_choice(self):
        """Every element in the ring must both beat something and lose to
        something, or one element would simply be the best in the game."""
        for el in BEATS:
            self.assertIn(el, BEATEN_BY, f"{el} beats something but nothing beats it")

    def test_nothing_beats_itself(self):
        for el, beaten in BEATS.items():
            self.assertNotEqual(el, beaten)

    def test_physical_is_neutral_in_both_directions(self):
        """Warriors and rogues are largely physical. If physical could be
        resisted they would be second-class in exactly the fights where they
        cannot switch element."""
        for el in list(BEATS) + [PHYSICAL]:
            self.assertEqual(matchup(PHYSICAL, el), 1.0, f"physical -> {el}")
            self.assertEqual(matchup(el, PHYSICAL), 1.0, f"{el} -> physical")

    def test_strong_and_weak_are_symmetric_opposites(self):
        for att, deff in BEATS.items():
            self.assertEqual(matchup(att, deff), STRONG_MULT)
            self.assertEqual(matchup(deff, att), WEAK_MULT)

    def test_the_bonus_stays_modest(self):
        """Calibrated to roughly offset the boss damage increase that shipped
        with it. A bigger number would make an off-element character unable to
        clear content their gear says they should."""
        self.assertLessEqual(STRONG_MULT, 1.25)
        self.assertGreaterEqual(WEAK_MULT, 0.80)


class TestEnemyElements(unittest.TestCase):
    def test_a_bosss_own_kit_decides_its_element(self):
        # Magmadar breathes lava; nothing about the string "magmadar" says fire.
        self.assertEqual(enemy_element("magmadar"), "fire")
        self.assertEqual(enemy_element("ancient_frost_giant"), "frost")
        self.assertEqual(enemy_element("spider_queen"), "nature")

    def test_every_enemy_resolves_to_a_known_element(self):
        allowed = set(BEATS) | {PHYSICAL}
        for key in ENEMIES:
            self.assertIn(enemy_element(key), allowed, f"{key} has an unknown element")

    def test_mundane_enemies_advertise_no_weakness(self):
        """A bandit has no elemental weakness. Inventing one would send players
        chasing a counter that does not exist."""
        p = enemy_element_payload("defias_bandit")
        self.assertEqual(p["element"], PHYSICAL)
        self.assertIsNone(p["weak_to"])
        self.assertIsNone(p["weak_to_label"])

    def test_an_elemental_enemy_names_what_beats_it(self):
        p = enemy_element_payload("magmadar")
        self.assertEqual(p["element"], "fire")
        self.assertEqual(p["weak_to"], BEATEN_BY["fire"])
        self.assertTrue(p["weak_to_label"])

    def test_unknown_and_missing_keys_degrade_to_physical(self):
        self.assertEqual(enemy_element(None), PHYSICAL)
        self.assertEqual(enemy_element("no_such_enemy_key"), PHYSICAL)

    def test_a_meaningful_share_of_the_roster_has_an_element(self):
        """If almost everything were physical the system would never fire."""
        elemental = sum(1 for k in ENEMIES if enemy_element(k) != PHYSICAL)
        self.assertGreater(elemental, len(ENEMIES) * 0.5)


class TestMatchupAppliesInCombat(unittest.TestCase):
    def _hit(self, ability_key, enemy_key, seed=9):
        random.seed(seed)
        e, p = _enemy(), _player()
        s = CombatSession(session_id=None, players=[p], enemies=[e], enemy_key=enemy_key)
        before = e.current_hp
        eng = CombatEngine()
        eng.use_ability(ability_key, p, [e], session=s)
        return before - e.current_hp

    def test_the_same_spell_hits_differently_in_different_fights(self):
        """The whole point: one character, one kit, different right answers."""
        vs_nature = self._hit("fireball", "spider_queen")   # fire beats nature
        vs_fire = self._hit("fireball", "magmadar")         # neutral
        vs_holy = self._hit("fireball", "goldshire_guard")  # holy beats fire
        self.assertGreater(vs_nature, vs_fire)
        self.assertGreater(vs_fire, vs_holy)

    def test_a_physical_ability_is_unaffected_by_the_matchup(self):
        a = self._hit("strike", "spider_queen")
        b = self._hit("strike", "magmadar")
        self.assertEqual(a, b)

    def test_enemies_do_not_get_matchups(self):
        """Deliberate scope: bosses just gained working signature moves and got
        harder. Elemental damage on top would stack two difficulty changes in one
        release and neither could be judged alone."""
        eng = CombatEngine()
        random.seed(3)
        e, p = _enemy(), _player()
        s = CombatSession(session_id=None, players=[p], enemies=[e], enemy_key="magmadar")
        eng.use_ability("lava_breath", e, [p], session=s)
        took_a = p.max_hp - p.current_hp

        random.seed(3)
        e2, p2 = _enemy(), _player()
        s2 = CombatSession(session_id=None, players=[p2], enemies=[e2], enemy_key="ancient_frost_giant")
        eng.use_ability("lava_breath", e2, [p2], session=s2)
        took_b = p2.max_hp - p2.current_hp
        self.assertEqual(took_a, took_b)

    def test_effectiveness_matches_the_damage_it_predicts(self):
        """The button says "strong"; the hit must actually be stronger. Checked
        against the real ring rather than a copy of it, so reordering BEATS
        cannot leave the marker lying."""
        for att_key, foe_key in (
            ("fireball", "spider_queen"),        # fire  -> nature
            ("frost_bolt", "ghost_admiral"),     # frost -> shadow
            ("smite", "magmadar"),               # holy  -> fire
        ):
            att, foe = ability_element(att_key), enemy_element(foe_key)
            self.assertEqual(BEATS[att], foe, f"test premise wrong for {att_key} vs {foe_key}")
            self.assertEqual(effectiveness(att, foe), "strong")
            # ...and the reverse pairing must read weak.
            self.assertEqual(effectiveness(foe, att), "weak")

        self.assertEqual(effectiveness(ability_element("strike"), enemy_element("magmadar")), "neutral")

    def test_every_player_ability_element_is_a_real_element(self):
        allowed = set(BEATS) | {PHYSICAL}
        for key in ABILITIES:
            self.assertIn(ability_element(key), allowed, f"{key}")


class TestBossPhases(unittest.TestCase):
    def test_phases_track_the_health_thresholds(self):
        eng = CombatEngine()
        b = _enemy(hp=1000)
        for pct, expected in ((100, 1), (51, 1), (50, 2), (26, 2), (25, 3), (1, 3)):
            b.current_hp = int(b.max_hp * pct / 100)
            self.assertEqual(eng.boss_phase(b), expected, f"at {pct}% HP")

    def test_a_cornered_boss_reaches_for_its_kit_more_often(self):
        """This is what makes a phase felt. The rate used to be a flat 0.35
        regardless of phase, so a boss at 5% health fought like one at 100%."""
        rates = [SIGNATURE_RATE_BY_PHASE[p] for p in (1, 2, 3)]
        self.assertEqual(rates, sorted(rates), "signature rate must not fall as the boss weakens")
        self.assertLess(rates[0], rates[-1])

    def test_every_phase_has_a_label_and_every_transition_a_line(self):
        for p in (1, 2, 3):
            self.assertTrue(PHASE_LABEL.get(p), f"phase {p} has no label")
        for p in PHASE_THRESHOLDS:
            self.assertIn(p, PHASE_ANNOUNCE, f"phase {p} is entered silently")
        self.assertNotIn(1, PHASE_ANNOUNCE, "phase 1 is not a transition")

    def test_phase_change_is_announced_once_and_not_on_the_way_back_up(self):
        from services.combat.activity_combat import _advance_boss_phase

        eng = CombatEngine()
        b = _enemy(hp=1000)
        s = CombatSession(session_id=None, players=[_player()], enemies=[b], is_boss=True)
        log: list = []

        _advance_boss_phase(eng, s, b, log)          # full health, phase 1
        self.assertEqual(log, [])

        b.current_hp = 400                            # crosses into phase 2
        _advance_boss_phase(eng, s, b, log)
        self.assertEqual(len(log), 1)

        _advance_boss_phase(eng, s, b, log)          # same phase, no repeat
        self.assertEqual(len(log), 1)

        b.current_hp = 900                            # healed back above 50%
        _advance_boss_phase(eng, s, b, log)
        self.assertEqual(len(log), 1, "announced a phase it had already been in")
        self.assertEqual(s.boss_phase, 1)

    def test_non_bosses_have_no_phase(self):
        from services.combat.activity_combat import _advance_boss_phase

        eng = CombatEngine()
        e = _enemy(hp=100)
        e.current_hp = 5
        s = CombatSession(session_id=None, players=[_player()], enemies=[e], is_boss=False)
        log: list = []
        _advance_boss_phase(eng, s, e, log)
        self.assertEqual(log, [])


if __name__ == "__main__":
    unittest.main()
