"""Boss signature moves and enemy intent.

Every boss template in config/settings.py declares a kit — Magmadar's
("lava_breath", "molten_armor"), Gorgoth's ("stone_skin", "petrify"), and so on
for 33 bosses across 39 keys. Only two of those keys existed in ABILITIES. The
other 37 fell through `ABILITIES.get(key, ABILITIES["auto_attack"])` and
resolved to a plain swing, so every named boss in the game fought exactly like
trash with a bigger health bar.

These tests exist so that can never silently happen again, and so the balance
rules the moves were designed under stay true.
"""
import random
import unittest

from config.settings import CLASSES, ENEMIES
from services.combat.combat_engine import (
    ABILITIES,
    BRACE_ABSORB_PCT,
    CombatEngine,
    CombatSession,
    Combatant,
    StatusEffect,
    intent_payload,
)
from services.combat.enemy_abilities import (
    ELEMENTAL_KEYS,
    ENEMY_ABILITY_SPECS,
    MAX_ENEMY_AOE_MULT,
    MAX_ENEMY_DMG_MULT,
    classify_intent,
)

KNOWN_KINDS = {"heavy", "sweep", "strike", "control", "empower", "guard"}


def _enemy(hp=4000, ap=800, armor=200):
    return Combatant(
        id="e", name="Boss", is_player=False, char_id=None,
        current_hp=hp, max_hp=hp, current_res=0, max_res=0, res_type="none",
        attack_power=ap, spell_power=ap, armor=armor,
        dmg_min=40, dmg_max=80, crit_chance=0.0,
    )


def _player(hp=2000):
    return Combatant(
        id="p", name="Hero", is_player=True, char_id=None,
        current_hp=hp, max_hp=hp, current_res=100, max_res=100, res_type="mana",
        attack_power=300, spell_power=300, armor=600,
        dmg_min=20, dmg_max=40, crit_chance=0.0, dodge_chance=0.0,
    )


class TestEveryDeclaredAbilityExists(unittest.TestCase):
    """The regression that started all of this."""

    def test_no_boss_declares_a_move_the_engine_does_not_have(self):
        missing = {}
        for key, tmpl in ENEMIES.items():
            for ab in (tmpl.abilities or ()):
                if ab not in ABILITIES:
                    missing.setdefault(ab, []).append(tmpl.name)
        self.assertEqual(
            missing, {},
            "These declared abilities have no entry in ABILITIES, so they "
            "silently resolve to auto_attack:\n"
            + "\n".join(f"  {k}: {', '.join(v)}" for k, v in sorted(missing.items())),
        )

    def test_the_thirty_seven_are_actually_wired(self):
        # Guards against the module existing but never being merged.
        for key in ENEMY_ABILITY_SPECS:
            self.assertIn(key, ABILITIES, f"{key} defined but not merged into ABILITIES")
            self.assertIsNot(
                ABILITIES[key], ABILITIES["auto_attack"],
                f"{key} still resolves to a plain swing",
            )


class TestBalanceRules(unittest.TestCase):
    def test_nothing_out_damages_the_pre_existing_ceiling(self):
        for key in ENEMY_ABILITY_SPECS:
            ab = ABILITIES[key]
            cap = MAX_ENEMY_AOE_MULT if ab.is_aoe else MAX_ENEMY_DMG_MULT
            self.assertLessEqual(
                ab.dmg_mult, cap,
                f"{key} at {ab.dmg_mult} exceeds the {'AoE' if ab.is_aoe else 'single-target'} cap of {cap}",
            )

    def test_every_signature_move_is_on_a_cooldown(self):
        """Cooldowns are the balance valve. Before this work nothing ever went
        on cooldown, because the auto_attack fallback has none — so a boss could
        roll its 'special' every single turn."""
        for key in ENEMY_ABILITY_SPECS:
            self.assertGreaterEqual(
                ABILITIES[key].cooldown, 3,
                f"{key} has no meaningful cooldown; it can be spammed",
            )

    def test_enemy_moves_cost_no_resource(self):
        # Enemies are built with max_res=0, so a move with a cost would either
        # never fire or fire for free depending on the check. Keep it explicit.
        for key in ENEMY_ABILITY_SPECS:
            self.assertEqual(ABILITIES[key].cost, 0, f"{key} has a resource cost")

    def test_elemental_moves_do_not_use_ignores_armor(self):
        """Pinned deliberately. `ignores_armor` routes damage through the
        resistance branch — and database/generate_items.py never grants
        resistance, so that branch applies no mitigation at all. Making these
        armour-ignoring measured at +73% to +80% boss damage. They cut through
        armour via armor_pen_pct instead."""
        for key in ELEMENTAL_KEYS:
            self.assertFalse(
                ABILITIES[key].ignores_armor,
                f"{key} ignores armour; with 0 resistance on all gear that is unmitigated damage",
            )


class TestTargetingIsCoherent(unittest.TestCase):
    def test_a_move_never_damages_its_target_and_buffs_it_too(self):
        """`applies` lands on whoever the ability targets. An AoE hit that also
        granted power_up would hand the buff to the players — which is exactly
        what the first draft of `summon` did."""
        buffs = {StatusEffect.SHIELD, StatusEffect.POWER_UP, StatusEffect.REGEN}
        for key in ENEMY_ABILITY_SPECS:
            ab = ABILITIES[key]
            if ab.applies in buffs:
                self.assertEqual(
                    ab.target, "self",
                    f"{key} applies a buff but targets {ab.target} — it would buff the players",
                )
                self.assertEqual(ab.dmg_mult, 0.0, f"{key} both buffs its caster and deals damage")

    def test_self_buffs_actually_land_on_the_caster(self):
        eng = CombatEngine()
        for key in ENEMY_ABILITY_SPECS:
            ab = ABILITIES[key]
            if ab.target != "self":
                continue
            e, p = _enemy(), _player()
            s = CombatSession(session_id=None, players=[p], enemies=[e])
            eng.use_ability(key, e, [p], session=s)
            self.assertTrue(e.has(ab.applies), f"{key} did not land on its caster")
            self.assertFalse(p.has(ab.applies), f"{key} leaked onto the player")

    def test_shields_and_dots_scale_with_the_combatant(self):
        """Flat effect_val is fine at level 5 and meaningless at level 60."""
        eng = CombatEngine()
        small, big = _enemy(hp=500, ap=100), _enemy(hp=50_000, ap=5_000)
        p1, p2 = _player(), _player()
        s1 = CombatSession(session_id=None, players=[p1], enemies=[small])
        s2 = CombatSession(session_id=None, players=[p2], enemies=[big])

        eng.use_ability("stone_skin", small, [p1], session=s1)
        eng.use_ability("stone_skin", big, [p2], session=s2)
        self.assertGreater(
            big.get_status(StatusEffect.SHIELD).value,
            small.get_status(StatusEffect.SHIELD).value * 10,
            "absorb barrier does not scale with the caster",
        )

        eng.use_ability("poison", small, [p1], session=s1)
        eng.use_ability("poison", big, [p2], session=s2)
        self.assertGreater(
            p2.get_status(StatusEffect.POISON).value,
            p1.get_status(StatusEffect.POISON).value * 10,
            "damage-over-time does not scale with the caster",
        )


class TestIntentIsHonest(unittest.TestCase):
    """Intent is only worth showing if it cannot be a bluff."""

    def test_what_is_telegraphed_is_what_executes(self):
        eng = CombatEngine()
        random.seed(1)
        for _ in range(300):
            e, p = _enemy(), _player()
            s = CombatSession(session_id=None, players=[p], enemies=[e],
                              is_boss=True, enemy_key="magmadar")
            eng.plan_enemy_turn(e, [p], True, 1, enemy_key="magmadar")
            promised = e.intent
            if not promised:
                continue
            used, _ = eng.enemy_turn(e, [p], True, 1, enemy_key="magmadar")
            self.assertEqual(used, promised, "the enemy did something other than what it telegraphed")

    def test_the_telegraph_is_consumed_not_replayed(self):
        eng = CombatEngine()
        e, p = _enemy(), _player()
        eng.plan_enemy_turn(e, [p], True, 1, enemy_key="magmadar")
        self.assertIsNotNone(e.intent)
        eng.enemy_turn(e, [p], True, 1, enemy_key="magmadar")
        self.assertIsNone(e.intent, "intent survived its own turn and would be shown again")

    def test_stunning_a_wind_up_cancels_it(self):
        """The best interaction in the design: read the telegraph, stun it, the
        move is lost rather than merely delayed."""
        eng = CombatEngine()
        e, p = _enemy(), _player()
        s = CombatSession(session_id=None, players=[p], enemies=[e], is_boss=True)
        e.intent = "crush"
        e.add_status(StatusEffect.STUN, 0, 1, "player")
        eng.tick_turn(e)  # sets is_stunned from the status
        ab, targets = eng.enemy_turn(e, [p], True, 1)
        before = p.current_hp
        eng.use_ability(ab, e, targets, session=s)
        self.assertEqual(p.current_hp, before, "a stunned enemy still landed its telegraphed hit")

    def test_intent_payload_covers_every_ability_a_boss_can_pick(self):
        for tmpl in ENEMIES.values():
            for key in (tmpl.abilities or ()):
                e = _enemy()
                e.intent = key
                payload = intent_payload(e)
                self.assertIsNotNone(payload, f"no intent payload for {key}")
                self.assertIn(payload["kind"], KNOWN_KINDS, f"{key} classified as {payload['kind']}")
                self.assertIn(payload["severity"], (1, 2, 3))
                self.assertTrue(payload["tell"], f"{key} has no wind-up line")

    def test_boss_ai_fallbacks_are_classifiable_too(self):
        # enemy_turn falls back to these for bosses with no template kit.
        for key in ("auto_attack", "mortal_strike", "whirlwind"):
            e = _enemy()
            e.intent = key
            self.assertIn(intent_payload(e)["kind"], KNOWN_KINDS)

    def test_no_intent_when_there_is_nothing_to_hit(self):
        eng = CombatEngine()
        e, p = _enemy(), _player()
        p.is_dead = True
        self.assertIsNone(eng.plan_enemy_turn(e, [p], True, 1, enemy_key="magmadar"))
        self.assertIsNone(e.intent)

    def test_elemental_moves_are_reported_as_elemental(self):
        """`elemental` cannot be read off `ignores_armor` — that flag is false by
        design (see TestBalanceRules), so reading it reported every boss move as
        plain physical and the UI never showed the armour-piercing chip."""
        e = _enemy()
        e.intent = "lava_breath"
        self.assertTrue(intent_payload(e)["elemental"])
        e.intent = "crush"
        self.assertFalse(intent_payload(e)["elemental"])

    def test_severity_ranks_a_heavy_hit_above_a_plain_one(self):
        heavy = classify_intent(ABILITIES["crush"])
        plain = classify_intent(ABILITIES["auto_attack"])
        self.assertEqual(heavy["kind"], "heavy")
        self.assertGreater(heavy["severity"], plain["severity"])


class TestBrace(unittest.TestCase):
    """Intent is only a decision if every class can answer it."""

    def test_brace_is_free(self):
        ab = ABILITIES["brace"]
        self.assertEqual(ab.cost, 0)
        self.assertEqual(ab.cost_type, "none")

    def test_every_class_is_offered_brace_from_level_one(self):
        """Checked against the real option builder, not a reimplementation of
        it — a class without an answer to the telegraph would make intent a
        spoiler rather than a decision."""
        from services.combat.activity_combat import _ability_options

        self.assertTrue(CLASSES, "no classes to check against")
        for cls_key in CLASSES:
            char = {"class": cls_key, "specialization": None, "level": 1}
            opts = _ability_options(char, _player())
            keys = {o["key"] for o in opts}
            self.assertIn("brace", keys, f"{cls_key} is never offered Brace")
            row = next(o for o in opts if o["key"] == "brace")
            self.assertIsNone(row["disabled"], f"Brace starts disabled for {cls_key}")

    def test_brace_absorbs_a_share_of_your_own_health(self):
        eng = CombatEngine()
        for hp in (200, 2_000, 40_000):
            p = _player(hp=hp)
            s = CombatSession(session_id=None, players=[p], enemies=[_enemy()])
            eng.use_ability("brace", p, [p], session=s)
            sh = p.get_status(StatusEffect.SHIELD)
            self.assertIsNotNone(sh, "brace granted no absorb")
            self.assertEqual(sh.value, max(1, int(hp * BRACE_ABSORB_PCT)))

    def test_brace_actually_reduces_the_hit_it_was_meant_for(self):
        eng = CombatEngine()
        random.seed(2)
        e, bare = _enemy(), _player()
        s1 = CombatSession(session_id=None, players=[bare], enemies=[e])
        eng.use_ability("crush", e, [bare], session=s1)
        took_bare = bare.max_hp - bare.current_hp

        random.seed(2)
        e2, braced = _enemy(), _player()
        s2 = CombatSession(session_id=None, players=[braced], enemies=[e2])
        eng.use_ability("brace", braced, [braced], session=s2)
        eng.use_ability("crush", e2, [braced], session=s2)
        took_braced = braced.max_hp - braced.current_hp

        self.assertLess(took_braced, took_bare, "bracing did not reduce the incoming hit")

    def test_brace_expires_so_it_cannot_be_stockpiled(self):
        eng = CombatEngine()
        p = _player()
        s = CombatSession(session_id=None, players=[p], enemies=[_enemy()])
        eng.use_ability("brace", p, [p], session=s)
        eng.tick_turn(p)
        self.assertFalse(p.has(StatusEffect.SHIELD), "brace absorb carried into a later turn")


if __name__ == "__main__":
    unittest.main()
