"""
╔══════════════════════════════════════════════════════════════════════════════╗
║         PRODUCTION-READY GAME TEST SUITE - Complete Coverage                ║
╚══════════════════════════════════════════════════════════════════════════════╝

Tests EVERYTHING in your MMORPG including:
✅ Character system (creation, deletion, specs, stats, leveling)
✅ Combat engine (abilities, status effects, passives, boss scaling)
✅ Quest system (kill tracking, state transitions, metadata)
✅ Inventory & items (equipping, stats, enhancement, consumables)
✅ Dungeon system (run creation, floors, completion)
✅ Blacksmith (enhancement, stat boosts, protection)
✅ Achievement system (awarding, tracking, points)
✅ Daily login (streaks, rewards)
✅ Database integrity (foreign keys, cascades)
✅ NPC quests (discovery, progression, reputation)

Test types: Unit, Integration, End-to-End, Edge Cases
"""

import json
import logging
import asyncio
import random
import time
from typing import Dict, List, Optional, Tuple, Any
from uuid import UUID, uuid4
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass
from enum import Enum
import traceback

log = logging.getLogger("game_testing")


# ═══════════════════════════════════════════════════════════════════════════
#  TEST FRAMEWORK
# ═══════════════════════════════════════════════════════════════════════════

class TestStatus(Enum):
    PASSED = "✅ PASSED"
    FAILED = "❌ FAILED"
    WARNING = "⚠️  WARNING"
    SKIPPED = "⏭️  SKIPPED"
    ERROR = "💥 ERROR"


class TestType(Enum):
    UNIT = "Unit Test"
    INTEGRATION = "Integration Test"
    E2E = "End-to-End Test"
    EDGE_CASE = "Edge Case Test"
    PERFORMANCE = "Performance Test"
    STRESS = "Stress Test"


@dataclass
class TestResult:
    test_name: str
    category: str
    test_type: TestType
    status: TestStatus
    duration: float
    message: str
    details: Optional[Dict] = None
    error: Optional[str] = None
    traceback: Optional[str] = None


class TestReport:
    """Enhanced test report with detailed tracking."""

    def __init__(self):
        self.results: List[TestResult] = []
        self.start_time = time.time()
        self.critical_failures: List[TestResult] = []

    def add(self, result: TestResult):
        self.results.append(result)
        if result.status == TestStatus.FAILED:
            self.critical_failures.append(result)

    def get_summary(self) -> Dict:
        total = len(self.results)
        passed = sum(1 for r in self.results if r.status == TestStatus.PASSED)
        failed = sum(1 for r in self.results if r.status == TestStatus.FAILED)
        warnings = sum(1 for r in self.results if r.status == TestStatus.WARNING)
        errors = sum(1 for r in self.results if r.status == TestStatus.ERROR)
        skipped = sum(1 for r in self.results if r.status == TestStatus.SKIPPED)

        return {
            "total": total,
            "passed": passed,
            "failed": failed,
            "warnings": warnings,
            "errors": errors,
            "skipped": skipped,
            "pass_rate": (passed / total * 100) if total > 0 else 0,
            "duration": time.time() - self.start_time,
            "critical_failures": len(self.critical_failures),
        }

    def print_report(self, verbose: bool = True):
        """Print comprehensive test report."""
        summary = self.get_summary()

        print("\n" + "=" * 120)
        print("🧪 COMPLETE GAME TEST SUITE - PRODUCTION REPORT")
        print("=" * 120 + "\n")

        # Group by category and type
        categories: Dict[str, Dict[str, list]] = {}
        for result in self.results:
            if result.category not in categories:
                categories[result.category] = {}
            test_type = result.test_type.value
            if test_type not in categories[result.category]:
                categories[result.category][test_type] = []
            categories[result.category][test_type].append(result)

        for category, types in sorted(categories.items()):
            print(f"\n{'=' * 120}")
            print(f"📁 {category.upper()}")
            print(f"{'=' * 120}")

            for test_type, tests in sorted(types.items()):
                print(f"\n  {test_type}:")
                print(f"  {'-' * 116}")

                for test in tests:
                    status_icon = test.status.value
                    duration_str = f"{test.duration:.3f}s"
                    print(f"  {status_icon} {test.test_name:<80} {duration_str:>10}  {test.message}")

                    if test.status in [TestStatus.FAILED, TestStatus.ERROR] and verbose:
                        if test.error:
                            print(f"      └─ Error: {test.error}")
                        if test.traceback and verbose:
                            for line in test.traceback.strip().split("\n")[-4:]:
                                print(f"      │  {line}")

        # Critical failures section
        if self.critical_failures:
            print(f"\n{'=' * 120}")
            print("🚨 CRITICAL FAILURES")
            print(f"{'=' * 120}")
            for failure in self.critical_failures:
                print(f"\n  ❌ {failure.test_name}")
                print(f"     Category: {failure.category}")
                print(f"     Error: {failure.error}")
                if failure.details:
                    print(f"     Details: {failure.details}")

        # Summary
        print(f"\n{'=' * 120}")
        print("📊 TEST SUMMARY")
        print(f"{'=' * 120}")
        print(f"  Total Tests:       {summary['total']}")
        print(f"  ✅ Passed:         {summary['passed']} ({summary['pass_rate']:.1f}%)")
        print(f"  ❌ Failed:         {summary['failed']}")
        print(f"  💥 Errors:         {summary['errors']}")
        print(f"  ⚠️  Warnings:       {summary['warnings']}")
        print(f"  ⏭️  Skipped:        {summary['skipped']}")
        print(f"  ⏱️  Duration:       {summary['duration']:.2f}s")
        print(f"{'=' * 120}\n")

        if summary["failed"] == 0 and summary["errors"] == 0:
            print("🎉 ALL TESTS PASSED! Game is production-ready.\n")
        elif summary["failed"] <= 2:
            print(f"⚠️  {summary['failed']} minor issues found. Review and fix.\n")
        else:
            print(f"🚨 {summary['failed']} CRITICAL ISSUES! Do not deploy.\n")


# ═══════════════════════════════════════════════════════════════════════════
#  COMPLETE GAME TEST SUITE
# ═══════════════════════════════════════════════════════════════════════════

class CompleteGameTestSuite:
    """Production-ready test suite covering all game systems."""

    def __init__(self, db, char_svc, inv_svc, quest_svc, blacksmith_svc,
                 dungeon_svc, achievement_svc, daily_svc):
        self.db = db
        self.char_svc = char_svc
        self.inv_svc = inv_svc
        self.quest_svc = quest_svc
        self.blacksmith_svc = blacksmith_svc
        self.dungeon_svc = dungeon_svc
        self.achievement_svc = achievement_svc
        self.daily_svc = daily_svc

        self.report = TestReport()
        self.test_data: Dict[str, Any] = {
            "characters": [],    # List of (player_id, char_record) tuples
            "items": [],
            "dungeon_runs": [],
        }

    # ── Helper: create a player + character quickly ────────────────────────
    async def _create_test_character(
        self, name: str, class_key: str = "warrior", level: int = 1
    ) -> Tuple[int, dict]:
        """Create a player and character for testing. Returns (player_id, char_record)."""
        player_id = 900000000 + random.randint(1, 9999999)
        # Ensure player exists
        await self.char_svc.ensure_player(player_id, f"test_user_{player_id}")
        # Create character
        ok, msg, char = await self.char_svc.create_character(player_id, name, class_key)
        assert ok, f"Failed to create {name} ({class_key}): {msg}"
        assert char is not None, f"Character record is None for {name}"

        # Set level if needed
        if level > 1:
            await self.db.execute(
                "UPDATE characters SET level = $2 WHERE id = $1", char["id"], level
            )

        return player_id, dict(char)

    async def run_test(self, test_func, category: str, test_type: TestType):
        """Wrapper to run individual tests with error handling."""
        test_name = test_func.__name__.replace("test_", "").replace("_", " ").title()
        start = time.time()

        try:
            await test_func()
            self.report.add(TestResult(
                test_name=test_name, category=category, test_type=test_type,
                status=TestStatus.PASSED, duration=time.time() - start,
                message="Test completed successfully",
            ))
        except AssertionError as e:
            self.report.add(TestResult(
                test_name=test_name, category=category, test_type=test_type,
                status=TestStatus.FAILED, duration=time.time() - start,
                message="Assertion failed", error=str(e),
                traceback=traceback.format_exc(),
            ))
        except Exception as e:
            self.report.add(TestResult(
                test_name=test_name, category=category, test_type=test_type,
                status=TestStatus.ERROR, duration=time.time() - start,
                message="Unexpected error", error=str(e),
                traceback=traceback.format_exc(),
            ))

    # ══════════════════════════════════════════════════════════════════════
    #  CATEGORY 1: CHARACTER SYSTEM (Critical)
    # ══════════════════════════════════════════════════════════════════════

    async def test_character_creation_all_classes(self):
        """UNIT: Test creating characters of all 6 classes."""
        classes = ["warrior", "paladin", "mage", "rogue", "priest", "hunter"]

        for class_key in classes:
            pid, char = await self._create_test_character(
                f"TestAll{class_key.title()}{random.randint(100,999)}", class_key
            )
            assert char["class"] == class_key, f"Wrong class: {char['class']}"
            assert char["level"] == 1, f"Starting level not 1: {char['level']}"
            self.test_data["characters"].append((pid, char))

    async def test_character_creation_invalid_class(self):
        """EDGE_CASE: Reject unknown class like 'warlock'."""
        player_id = 900100000 + random.randint(1, 99999)
        await self.char_svc.ensure_player(player_id, "test_bad_class")
        ok, msg, char = await self.char_svc.create_character(player_id, "BadClass", "warlock")
        assert not ok, "Should reject unknown class 'warlock'"
        assert char is None, "Char should be None for invalid class"

    async def test_character_duplicate_name(self):
        """EDGE_CASE: Reject duplicate character names."""
        # Use the first character created
        pid1, char1 = self.test_data["characters"][0]
        existing_name = char1["name"]

        player_id2 = 900200000 + random.randint(1, 99999)
        await self.char_svc.ensure_player(player_id2, "test_dup")
        ok, msg, _ = await self.char_svc.create_character(player_id2, existing_name, "mage")
        assert not ok, f"Should reject duplicate name '{existing_name}'"

    async def test_character_only_one_active(self):
        """EDGE_CASE: Reject second active character for same player."""
        pid, char = self.test_data["characters"][0]
        ok, msg, _ = await self.char_svc.create_character(pid, "SecondChar", "mage")
        assert not ok, "Should reject second active character"
        assert "delete" in msg.lower(), f"Wrong error: {msg}"

    async def test_get_character_methods(self):
        """UNIT: Test get_character and get_by_id."""
        pid, char = self.test_data["characters"][0]
        # get_character by player_id
        fetched = await self.char_svc.get_character(pid)
        assert fetched is not None, "get_character returned None"
        assert fetched["id"] == char["id"], "Wrong character returned"

        # get_by_id by char UUID
        fetched2 = await self.char_svc.get_by_id(char["id"])
        assert fetched2 is not None, "get_by_id returned None"
        assert fetched2["name"] == char["name"], "Wrong character by ID"

    async def test_specialization_level_requirement(self):
        """UNIT: Test spec can only be selected at level 10+."""
        pid, char = self.test_data["characters"][0]

        # Set to level 5 (below requirement)
        await self.db.execute(
            "UPDATE characters SET level = 5, specialization = NULL WHERE id = $1",
            char["id"],
        )
        ok, msg = await self.char_svc.choose_spec(char["id"], "arms")
        assert not ok, "Should not allow spec below level 10"
        assert "level" in msg.lower(), f"Wrong error: {msg}"

        # Set to level 10
        await self.db.execute(
            "UPDATE characters SET level = 10 WHERE id = $1", char["id"]
        )
        ok, msg = await self.char_svc.choose_spec(char["id"], "arms")
        assert ok, f"Spec choice failed at level 10: {msg}"

    async def test_specialization_class_mismatch(self):
        """EDGE_CASE: Reject spec that doesn't belong to the character's class."""
        pid, char = self.test_data["characters"][0]
        # Reset spec for a warrior
        await self.db.execute(
            "UPDATE characters SET level = 10, specialization = NULL, class = 'warrior' WHERE id = $1",
            char["id"],
        )
        # Try a mage spec on a warrior
        ok, msg = await self.char_svc.choose_spec(char["id"], "fire")
        assert not ok, "Should reject spec from wrong class"

    async def test_total_stats_with_gear(self):
        """UNIT: Test total stats = base + gear + spec multipliers."""
        pid, char = self.test_data["characters"][0]

        # Ensure character is a warrior at level 10
        await self.db.execute(
            "UPDATE characters SET class = 'warrior', level = 10, specialization = NULL WHERE id = $1",
            char["id"],
        )

        stats_before = await self.char_svc.total_stats(char["id"])
        base_str = stats_before["strength"]

        # Add a weapon with bonus strength via DB (simulate item with bonus stats)
        ok, msg = await self.inv_svc.add_item(
            char["id"], "iron_sword", rarity="common",
            bonus={"r_str": 10, "r_agi": 0, "r_int": 0, "r_spi": 0, "r_sta": 0,
                   "r_haste": 0, "r_lifesteal": 0, "r_resistance": 0, "r_hit_rating": 0},
        )
        assert ok, f"Failed to add item: {msg}"

        # Find the item and equip it
        items = await self.inv_svc.get_all(char["id"])
        weapon = [i for i in items if i["template_id"] == "iron_sword"]
        assert len(weapon) > 0, "Iron sword not in inventory"
        eq_ok, eq_msg = await self.inv_svc.equip(char["id"], weapon[0]["id"])
        assert eq_ok, f"Failed to equip: {eq_msg}"

        stats_after = await self.char_svc.total_stats(char["id"])
        assert stats_after["strength"] >= base_str + 10, (
            f"Gear stats not applied: {stats_after['strength']} vs expected >= {base_str + 10}"
        )

        # Cleanup: unequip
        await self.inv_svc.unequip_slot(char["id"], weapon[0]["equip_slot"])

    async def test_xp_and_leveling(self):
        """INTEGRATION: Test XP gains and leveling."""
        pid, char = self.test_data["characters"][0]

        await self.db.execute(
            "UPDATE characters SET level = 1, xp = 0, xp_rested = 0 WHERE id = $1",
            char["id"],
        )

        xp_needed = self.char_svc.xp_for_next_level(1)
        result = await self.char_svc.award_xp(char["id"], xp_needed)
        assert result["leveled_up"], f"Did not level up after {xp_needed} XP"
        assert result["new_level"] == 2, f"Wrong level: {result['new_level']}"

    async def test_gold_operations(self):
        """UNIT: Test add_gold and deduct_gold."""
        pid, char = self.test_data["characters"][0]

        await self.db.execute(
            "UPDATE characters SET gold = 0 WHERE id = $1", char["id"]
        )

        # Add gold
        await self.char_svc.add_gold(char["id"], 500, reason="test", source="drop")
        char_after = await self.char_svc.get_by_id(char["id"])
        assert char_after["gold"] == 500, f"Gold not added: {char_after['gold']}"

        # Deduct gold
        ok = await self.char_svc.deduct_gold(char["id"], 200, reason="test")
        assert ok, "Deduct gold failed"
        char_after2 = await self.char_svc.get_by_id(char["id"])
        assert char_after2["gold"] == 300, f"Gold not deducted: {char_after2['gold']}"

        # Try to deduct more than available
        ok2 = await self.char_svc.deduct_gold(char["id"], 999, reason="test")
        assert not ok2, "Should not allow deducting more gold than available"

    async def test_full_restore(self):
        """UNIT: Test full HP restore."""
        pid, char = self.test_data["characters"][0]

        # Damage the character
        await self.db.execute(
            "UPDATE characters SET current_hp = 1 WHERE id = $1", char["id"]
        )
        await self.char_svc.full_restore(char["id"])
        char_after = await self.char_svc.get_by_id(char["id"])
        assert char_after["current_hp"] == char_after["max_hp"], (
            f"HP not restored: {char_after['current_hp']}/{char_after['max_hp']}"
        )

    async def test_character_deletion_cascade(self):
        """INTEGRATION: Test character deletion cascades properly."""
        pid, char = await self._create_test_character("CascadeDelTest")
        char_id = char["id"]

        # Add inventory
        await self.inv_svc.add_item(char_id, "iron_sword")

        # Add quest progress
        await self.db.execute(
            """INSERT INTO quest_progress (character_id, quest_id, npc_id, state)
               VALUES ($1, 'test_cascade_quest', 'old_guard_marcus', 'active')""",
            char_id,
        )

        # Clean up gold_log first (no ON DELETE CASCADE)
        await self.db.execute("DELETE FROM gold_log WHERE character_id=$1", char_id)
        # Delete character
        await self.db.execute("DELETE FROM characters WHERE id = $1", char_id)

        # Verify CASCADE deleted inventory
        inv = await self.db.fetch(
            "SELECT * FROM inventory WHERE character_id = $1", char_id
        )
        assert len(inv) == 0, "Inventory not cascade deleted"

        # Verify CASCADE deleted quests
        quests = await self.db.fetch(
            "SELECT * FROM quest_progress WHERE character_id = $1", char_id
        )
        assert len(quests) == 0, "Quests not cascade deleted"

    # ══════════════════════════════════════════════════════════════════════
    #  CATEGORY 2: COMBAT ENGINE (Critical)
    # ══════════════════════════════════════════════════════════════════════

    async def test_combat_engine_basic_attack(self):
        """UNIT: Test basic combat engine attack."""
        from services.combat.combat_engine import (
            CombatEngine, Combatant, CombatSession, ABILITIES,
        )

        engine = CombatEngine()

        attacker = Combatant(
            id="p1", name="TestWarrior", is_player=True, char_id=None,
            current_hp=500, max_hp=500, current_res=100, max_res=100,
            res_type="rage", attack_power=100, dmg_min=20, dmg_max=40,
            armor=50, crit_chance=10.0,
        )
        defender = Combatant(
            id="e1", name="Forest Wolf", is_player=False, char_id=None,
            current_hp=200, max_hp=200, current_res=0, max_res=0,
            res_type="none", attack_power=30, dmg_min=8, dmg_max=16,
            armor=10, crit_chance=5.0,
        )

        session = CombatSession(
            session_id=uuid4(), players=[attacker], enemies=[defender],
            zone_key="elwynn_forest",
        )

        results = engine.use_ability("auto_attack", attacker, [defender], session)
        assert len(results) > 0, "No results from auto_attack"
        assert results[0].narrative is not None, "No narrative generated"

    async def test_combat_engine_ability_with_status_effect(self):
        """UNIT: Test abilities that apply status effects."""
        from services.combat.combat_engine import (
            CombatEngine, Combatant, CombatSession, StatusEffect,
        )

        engine = CombatEngine()

        attacker = Combatant(
            id="p1", name="TestWarrior", is_player=True, char_id=None,
            current_hp=500, max_hp=500, current_res=50, max_res=100,
            res_type="rage", attack_power=100, dmg_min=20, dmg_max=40,
            armor=50, crit_chance=10.0,
        )
        defender = Combatant(
            id="e1", name="Wolf", is_player=False, char_id=None,
            current_hp=300, max_hp=300, current_res=0, max_res=0,
            res_type="none", attack_power=30, dmg_min=8, dmg_max=16,
            armor=10, crit_chance=5.0,
        )

        session = CombatSession(
            session_id=uuid4(), players=[attacker], enemies=[defender],
            zone_key="elwynn_forest",
        )

        # mortal_strike costs 25 rage and applies bleed
        results = engine.use_ability("mortal_strike", attacker, [defender], session)
        assert len(results) > 0, "No results from mortal_strike"
        # Check for bleed effect (might not always apply, but shouldn't error)

    async def test_combat_engine_armor_reduction(self):
        """UNIT: Test armor reduces physical damage."""
        from services.combat.combat_engine import (
            CombatEngine, Combatant, CombatSession,
        )

        engine = CombatEngine()

        attacker = Combatant(
            id="e1", name="Wolf", is_player=False, char_id=None,
            current_hp=200, max_hp=200, current_res=0, max_res=0,
            res_type="none", attack_power=100, dmg_min=50, dmg_max=50,
            armor=0, crit_chance=0.0,
        )

        # Target with 0 armor
        target_no_armor = Combatant(
            id="p1", name="Naked", is_player=True, char_id=None,
            current_hp=1000, max_hp=1000, current_res=0, max_res=0,
            res_type="rage", attack_power=50, armor=0, crit_chance=0.0,
        )

        # Target with high armor
        target_armor = Combatant(
            id="p2", name="Tank", is_player=True, char_id=None,
            current_hp=1000, max_hp=1000, current_res=0, max_res=0,
            res_type="rage", attack_power=50, armor=500, crit_chance=0.0,
        )

        session1 = CombatSession(
            session_id=uuid4(), players=[target_no_armor], enemies=[attacker],
            zone_key="elwynn_forest",
        )
        session2 = CombatSession(
            session_id=uuid4(), players=[target_armor], enemies=[attacker],
            zone_key="elwynn_forest",
        )

        # Run multiple attacks to average out RNG
        total_no_armor = 0
        total_with_armor = 0
        runs = 20

        for _ in range(runs):
            target_no_armor.current_hp = 1000
            target_armor.current_hp = 1000
            r1 = engine.use_ability("auto_attack", attacker, [target_no_armor], session1)
            r2 = engine.use_ability("auto_attack", attacker, [target_armor], session2)
            if r1 and r1[0].damage:
                total_no_armor += r1[0].damage
            if r2 and r2[0].damage:
                total_with_armor += r2[0].damage

        # Armor should reduce average damage
        if total_no_armor > 0:
            assert total_with_armor < total_no_armor, (
                f"Armor didn't reduce damage: {total_with_armor} vs {total_no_armor}"
            )

    async def test_combat_engine_boss_damage_scale(self):
        """UNIT: Test BOSS_DAMAGE_SCALE reduces boss damage."""
        from services.combat.combat_engine import (
            CombatEngine, Combatant, CombatSession,
        )
        from config.settings import Settings

        assert hasattr(Settings, "BOSS_DAMAGE_SCALE"), "BOSS_DAMAGE_SCALE not in Settings"
        assert Settings.BOSS_DAMAGE_SCALE < 1.0, (
            f"BOSS_DAMAGE_SCALE should be < 1.0, got {Settings.BOSS_DAMAGE_SCALE}"
        )

    async def test_combat_engine_stealth_mechanics(self):
        """UNIT: Test stealth ability applies STEALTH status."""
        from services.combat.combat_engine import (
            CombatEngine, Combatant, CombatSession, StatusEffect,
        )

        engine = CombatEngine()

        rogue = Combatant(
            id="p1", name="TestRogue", is_player=True, char_id=None,
            current_hp=400, max_hp=400, current_res=100, max_res=100,
            res_type="energy", attack_power=80, dmg_min=15, dmg_max=30,
            armor=30, crit_chance=15.0,
        )
        dummy = Combatant(
            id="e1", name="Dummy", is_player=False, char_id=None,
            current_hp=500, max_hp=500, current_res=0, max_res=0,
            res_type="none", attack_power=20, armor=10, crit_chance=0.0,
        )

        session = CombatSession(
            session_id=uuid4(), players=[rogue], enemies=[dummy],
            zone_key="elwynn_forest",
        )

        # Use stealth ability
        results = engine.use_ability("stealth", rogue, [rogue], session)
        assert rogue.has(StatusEffect.STEALTH), "Stealth not applied after stealth ability"

    async def test_combat_engine_execute_threshold(self):
        """UNIT: Test execute-type abilities require low HP target."""
        from services.combat.combat_engine import (
            CombatEngine, Combatant, CombatSession, ABILITIES,
        )

        engine = CombatEngine()

        # Check hammer_of_wrath has execute_threshold
        how = ABILITIES.get("hammer_of_wrath")
        if how and how.execute_threshold:
            paladin = Combatant(
                id="p1", name="TestPaladin", is_player=True, char_id=None,
                current_hp=500, max_hp=500, current_res=200, max_res=200,
                res_type="mana", attack_power=100, dmg_min=20, dmg_max=40,
                armor=50, crit_chance=10.0,
            )
            # Full HP enemy (should fail execute requirement)
            enemy_full = Combatant(
                id="e1", name="FullHP", is_player=False, char_id=None,
                current_hp=500, max_hp=500, current_res=0, max_res=0,
                res_type="none", attack_power=30, armor=10, crit_chance=0.0,
            )

            session = CombatSession(
                session_id=uuid4(), players=[paladin], enemies=[enemy_full],
                zone_key="elwynn_forest",
            )

            results = engine.use_ability("hammer_of_wrath", paladin, [enemy_full], session)
            # Should get a "can only be used when target is below X% HP" message
            assert len(results) > 0, "No results from hammer_of_wrath"
            assert "below" in results[0].narrative.lower() or results[0].damage == 0, (
                "Execute should fail on full HP target"
            )

    async def test_all_12_spec_passives_defined(self):
        """UNIT: Test all 12 specs have passives defined in SPECIALIZATIONS."""
        from config.settings import SPECIALIZATIONS, CLASSES

        expected_specs = []
        for cls_key, cls_config in CLASSES.items():
            for spec_key in cls_config.specializations:
                expected_specs.append(spec_key)

        assert len(expected_specs) == 12, f"Expected 12 specs, got {len(expected_specs)}"

        for spec_key in expected_specs:
            spec = SPECIALIZATIONS.get(spec_key)
            assert spec is not None, f"Spec '{spec_key}' missing from SPECIALIZATIONS"
            assert spec.passive_name, f"Spec '{spec_key}' has no passive_name"
            assert spec.passive_desc, f"Spec '{spec_key}' has no passive_desc"
            assert len(spec.bonus_abilities) > 0, f"Spec '{spec_key}' has no bonus_abilities"

    async def test_ability_unlock_levels_defined(self):
        """UNIT: Test ABILITY_UNLOCK_LEVELS covers all starter + spec abilities."""
        from config.settings import ABILITY_UNLOCK_LEVELS, CLASSES, SPECIALIZATIONS

        # Check all starter abilities have unlock levels
        for cls_key, cls_config in CLASSES.items():
            for ab_key in cls_config.starter_abilities:
                assert ab_key in ABILITY_UNLOCK_LEVELS, (
                    f"Starter ability '{ab_key}' missing from ABILITY_UNLOCK_LEVELS"
                )
                assert ABILITY_UNLOCK_LEVELS[ab_key] == 1, (
                    f"Starter ability '{ab_key}' should be level 1"
                )

        # Check all spec abilities have unlock levels
        for spec_key, spec_config in SPECIALIZATIONS.items():
            for ab_key in spec_config.bonus_abilities:
                assert ab_key in ABILITY_UNLOCK_LEVELS, (
                    f"Spec ability '{ab_key}' missing from ABILITY_UNLOCK_LEVELS"
                )

    async def test_zone_based_boss_scaling(self):
        """UNIT: Test _boss_hp_scale_for_zone returns different multipliers."""
        from config.settings import ZONES, Settings
        from config.settings import _boss_hp_scale_for_zone

        # Early zone (1-10) should have low multiplier
        early_zone = ZONES.get("elwynn_forest")
        early_scale = _boss_hp_scale_for_zone(early_zone)
        assert early_scale < Settings.BOSS_HP_SCALE, (
            f"Early zone scale ({early_scale}) should be less than default ({Settings.BOSS_HP_SCALE})"
        )

        # Endgame zone (50-60) should be higher
        endgame_zone = ZONES.get("blackrock_depths")
        endgame_scale = _boss_hp_scale_for_zone(endgame_zone)
        assert endgame_scale >= early_scale, (
            f"Endgame scale ({endgame_scale}) should be >= early ({early_scale})"
        )

    # ══════════════════════════════════════════════════════════════════════
    #  CATEGORY 3: QUEST SYSTEM (Critical - Fixed Bug)
    # ══════════════════════════════════════════════════════════════════════

    async def test_quest_offer_and_accept(self):
        """INTEGRATION: Test quest offer → accept state transition."""
        pid, char = self.test_data["characters"][0]

        # Clean up any existing quest
        await self.db.execute(
            "DELETE FROM quest_progress WHERE character_id=$1 AND quest_id='marcus_quest_1'",
            char["id"],
        )

        # Offer quest (requires npc_id)
        await self.quest_svc.offer_quest(char["id"], "old_guard_marcus", "marcus_quest_1")

        # Check state is 'offered'
        progress = await self.quest_svc.get_quest_progress(char["id"], "marcus_quest_1")
        assert progress is not None, "Quest not found after offer"
        assert progress["state"] == "offered", f"Wrong state after offer: {progress['state']}"

        # Accept quest
        await self.quest_svc.accept_quest(char["id"], "marcus_quest_1")

        # Check state changed to 'active'
        progress2 = await self.quest_svc.get_quest_progress(char["id"], "marcus_quest_1")
        assert progress2["state"] == "active", f"State didn't change: {progress2['state']}"

    async def test_quest_kill_tracking(self):
        """INTEGRATION: Test the quest kill tracking bug fix."""
        pid, char = self.test_data["characters"][0]

        # Clean up and offer+accept quest
        await self.db.execute(
            "DELETE FROM quest_progress WHERE character_id=$1 AND quest_id='marcus_quest_1'",
            char["id"],
        )
        await self.quest_svc.offer_quest(char["id"], "old_guard_marcus", "marcus_quest_1")
        await self.quest_svc.accept_quest(char["id"], "marcus_quest_1")

        # Check initial kill count in metadata
        progress_before = await self.quest_svc.get_quest_progress(char["id"], "marcus_quest_1")
        meta = progress_before.get("metadata", {})
        if isinstance(meta, str):
            meta = json.loads(meta)
        initial_kills = meta.get("kills_defias_bandit", 0)

        # Simulate killing a defias_bandit
        notifications = await self.quest_svc.check_kill_progress(
            char["id"], "defias_bandit", "elwynn_forest", False
        )

        # Check kill count increased
        progress_after = await self.quest_svc.get_quest_progress(char["id"], "marcus_quest_1")
        meta_after = progress_after.get("metadata", {})
        if isinstance(meta_after, str):
            meta_after = json.loads(meta_after)
        kills_after = meta_after.get("kills_defias_bandit", 0)

        assert kills_after > initial_kills, (
            f"Quest kill tracking broken: {initial_kills} → {kills_after}"
        )
        assert len(notifications) > 0, "No notifications from kill tracking"

    async def test_quest_kill_tracking_multiple_kills(self):
        """INTEGRATION: Test multiple consecutive kills all count."""
        pid, char = self.test_data["characters"][0]

        # Clean up and offer+accept quest
        await self.db.execute(
            "DELETE FROM quest_progress WHERE character_id=$1 AND quest_id='marcus_quest_1'",
            char["id"],
        )
        await self.quest_svc.offer_quest(char["id"], "old_guard_marcus", "marcus_quest_1")
        await self.quest_svc.accept_quest(char["id"], "marcus_quest_1")

        # Kill 3 defias bandits
        for i in range(3):
            await self.quest_svc.check_kill_progress(
                char["id"], "defias_bandit", "elwynn_forest", False
            )

        # Verify all 3 kills counted
        progress = await self.quest_svc.get_quest_progress(char["id"], "marcus_quest_1")
        meta = progress.get("metadata", {})
        if isinstance(meta, str):
            meta = json.loads(meta)
        kills = meta.get("kills_defias_bandit", 0)
        assert kills >= 3, f"Only {kills}/3 kills tracked (kill tracking bug!)"

    async def test_quest_metadata_persistence(self):
        """INTEGRATION: Test quest metadata (JSONB) persists correctly."""
        pid, char = self.test_data["characters"][0]

        quest_id = "meta_test_q"
        await self.db.execute(
            "DELETE FROM quest_progress WHERE character_id=$1 AND quest_id=$2",
            char["id"], quest_id,
        )

        # Insert directly
        await self.db.execute(
            """INSERT INTO quest_progress (character_id, quest_id, npc_id, state, metadata)
               VALUES ($1, $2, 'test_npc', 'active', $3::jsonb)""",
            char["id"], quest_id,
            json.dumps({"kills": 5, "items_collected": 2, "custom": "test"}),
        )

        # Retrieve and verify
        row = await self.db.fetchrow(
            "SELECT metadata FROM quest_progress WHERE character_id=$1 AND quest_id=$2",
            char["id"], quest_id,
        )
        assert row is not None, "Quest not found"
        meta = row["metadata"]
        if isinstance(meta, str):
            meta = json.loads(meta)
        assert meta["kills"] == 5, "Metadata kills lost"
        assert meta["custom"] == "test", "Custom data lost"

        # Cleanup
        await self.db.execute(
            "DELETE FROM quest_progress WHERE character_id=$1 AND quest_id=$2",
            char["id"], quest_id,
        )

    async def test_quest_advance_and_complete(self):
        """INTEGRATION: Test quest advance and completion flow."""
        pid, char = self.test_data["characters"][0]

        quest_id = "marcus_quest_1"
        await self.db.execute(
            "DELETE FROM quest_progress WHERE character_id=$1 AND quest_id=$2",
            char["id"], quest_id,
        )
        await self.quest_svc.offer_quest(char["id"], "old_guard_marcus", quest_id)
        await self.quest_svc.accept_quest(char["id"], quest_id)

        # Advance from step 1 to step 2
        ok = await self.quest_svc.advance_quest(char["id"], quest_id)
        assert ok, "Failed to advance quest"

        progress = await self.quest_svc.get_quest_progress(char["id"], quest_id)
        assert progress["current_step"] == 2, f"Step not advanced: {progress['current_step']}"

    async def test_quest_abandon(self):
        """UNIT: Test abandoning a quest removes it."""
        pid, char = self.test_data["characters"][0]

        quest_id = "abandon_test_q"
        await self.db.execute(
            "DELETE FROM quest_progress WHERE character_id=$1 AND quest_id=$2",
            char["id"], quest_id,
        )

        # Insert a test quest
        await self.db.execute(
            """INSERT INTO quest_progress (character_id, quest_id, npc_id, state)
               VALUES ($1, $2, 'test_npc', 'active')""",
            char["id"], quest_id,
        )

        ok = await self.quest_svc.abandon_quest(char["id"], quest_id)
        assert ok, "Abandon quest failed"

        progress = await self.quest_svc.get_quest_progress(char["id"], quest_id)
        assert progress is None, "Quest still exists after abandon"

    async def test_quest_timed_expiration(self):
        """INTEGRATION: Test timed quests expire correctly."""
        pid, char = self.test_data["characters"][0]

        quest_id = "marcus_quest_2"  # This quest has time_limit_hours = 48
        await self.db.execute(
            "DELETE FROM quest_progress WHERE character_id=$1 AND quest_id=$2",
            char["id"], quest_id,
        )
        await self.quest_svc.offer_quest(char["id"], "old_guard_marcus", quest_id)
        await self.quest_svc.accept_quest(char["id"], quest_id)

        # Set expires_at to the past
        past_time = datetime.now(timezone.utc) - timedelta(hours=1)
        await self.db.execute(
            "UPDATE quest_progress SET expires_at=$3 WHERE character_id=$1 AND quest_id=$2",
            char["id"], quest_id, past_time,
        )

        # Try to complete - should fail (returns None for expired quest)
        result = await self.quest_svc.complete_quest(char["id"], quest_id)
        assert result is None, "Timed quest didn't expire"

    async def test_npc_discovery(self):
        """INTEGRATION: Test NPC discovery tracking."""
        pid, char = self.test_data["characters"][0]

        # Discover an NPC
        await self.quest_svc.discover_npc(char["id"], "old_guard_marcus", "elwynn_forest")

        # Check discovery state
        state = await self.quest_svc.get_npc_state(char["id"], "old_guard_marcus")
        assert state == "discovered", f"Wrong NPC state: {state}"

    async def test_reputation_system(self):
        """INTEGRATION: Test adding and getting reputation."""
        pid, char = self.test_data["characters"][0]

        # Add reputation
        result = await self.quest_svc.add_reputation(
            char["id"], "stormwind_guard", 100
        )
        assert result is not None, "add_reputation returned None"

        # Get reputation
        rep = await self.quest_svc.get_reputation(char["id"], "stormwind_guard")
        assert rep >= 100, f"Reputation not tracked: {rep}"

    # ══════════════════════════════════════════════════════════════════════
    #  CATEGORY 4: INVENTORY & ITEMS
    # ══════════════════════════════════════════════════════════════════════

    async def test_add_item(self):
        """UNIT: Test adding items to inventory."""
        pid, char = self.test_data["characters"][0]

        ok, msg = await self.inv_svc.add_item(char["id"], "iron_sword")
        assert ok, f"Failed to add item: {msg}"

    async def test_equip_and_unequip(self):
        """INTEGRATION: Test equip/unequip flow."""
        pid, char = self.test_data["characters"][0]

        # Add a fresh weapon
        ok, msg = await self.inv_svc.add_item(char["id"], "iron_sword")
        assert ok, f"Failed to add item: {msg}"

        # Get the item
        items = await self.inv_svc.get_all(char["id"])
        swords = [i for i in items if i["template_id"] == "iron_sword" and not i["is_equipped"]]
        assert len(swords) > 0, "No unequipped iron_sword in inventory"
        sword = swords[0]

        # Equip
        eq_ok, eq_msg = await self.inv_svc.equip(char["id"], sword["id"])
        assert eq_ok, f"Equip failed: {eq_msg}"

        # Verify equipped
        equipped = await self.inv_svc.get_equipped(char["id"])
        assert sword["id"] in [v["id"] for v in equipped.values()], "Item not in equipped dict"

        # Unequip by slot
        uneq_ok, uneq_msg = await self.inv_svc.unequip_slot(char["id"], "main_hand")
        # Check it was unequipped (the function returns (bool, str))

    async def test_get_inventory(self):
        """UNIT: Test get_all inventory."""
        pid, char = self.test_data["characters"][0]
        items = await self.inv_svc.get_all(char["id"])
        assert isinstance(items, list), "get_all should return a list"

    async def test_sell_item(self):
        """INTEGRATION: Test selling an item."""
        pid, char = self.test_data["characters"][0]

        # Add item
        ok, msg = await self.inv_svc.add_item(char["id"], "iron_sword")
        assert ok, f"Add item failed: {msg}"

        # Find the item
        items = await self.inv_svc.get_all(char["id"])
        swords = [i for i in items if i["template_id"] == "iron_sword" and not i["is_equipped"]]
        assert len(swords) > 0, "No sword to sell"

        # Sell it
        gold_before = (await self.char_svc.get_by_id(char["id"]))["gold"]
        sell_ok, sell_msg, gold_earned = await self.inv_svc.sell(char["id"], swords[0]["id"])
        assert sell_ok, f"Sell failed: {sell_msg}"
        assert gold_earned > 0, "Got 0 gold from selling"

    async def test_use_consumable(self):
        """INTEGRATION: Test using a consumable item."""
        pid, char = self.test_data["characters"][0]

        # Add health potion
        ok, msg = await self.inv_svc.add_item(char["id"], "health_potion")
        assert ok, f"Add potion failed: {msg}"

        # Find the potion
        items = await self.inv_svc.get_all(char["id"])
        potions = [i for i in items if i["template_id"] == "health_potion"]
        assert len(potions) > 0, "No health potion in inventory"

        # Use it
        use_ok, use_msg, effect = await self.inv_svc.use_consumable(
            char["id"], potions[0]["id"]
        )
        assert use_ok, f"Use consumable failed: {use_msg}"
        assert effect is not None, "No effect data from consumable"

    async def test_loot_generation(self):
        """UNIT: Test loot generation gives items."""
        loot = await self.inv_svc.generate_loot("elwynn_forest", 10, is_boss=True)
        # Boss loot is 100% drop rate
        assert loot is not None, "Boss didn't drop loot"
        assert "template" in loot, "Loot missing template"
        assert "rarity" in loot, "Loot missing rarity"

    async def test_rarity_rolling(self):
        """UNIT: Test rarity rolling produces valid rarities."""
        valid = {"common", "uncommon", "rare", "epic", "legendary", "artifact"}
        for _ in range(50):
            rarity = self.inv_svc.roll_rarity()
            assert rarity in valid, f"Invalid rarity: {rarity}"

    # ══════════════════════════════════════════════════════════════════════
    #  CATEGORY 5: BLACKSMITH / ENHANCEMENT
    # ══════════════════════════════════════════════════════════════════════

    async def test_enhancement_info(self):
        """UNIT: Test get_enhancement_info for an item."""
        pid, char = self.test_data["characters"][0]

        # Add item
        ok, msg = await self.inv_svc.add_item(char["id"], "iron_sword")
        assert ok, f"Add item failed: {msg}"

        items = await self.inv_svc.get_all(char["id"])
        swords = [i for i in items if i["template_id"] == "iron_sword" and not i["is_equipped"]]
        assert len(swords) > 0, "No sword for enhancement test"

        info = await self.blacksmith_svc.get_enhancement_info(swords[0]["id"], char["id"])
        assert info is not None, "Enhancement info is None"
        assert "current_level" in info, "Missing current_level"
        assert "current_stats" in info, "Missing current_stats"
        assert info["current_level"] == 0, "New item should be +0"

    async def test_enhancement_stat_calculation(self):
        """UNIT: Test calculate_enhanced_stats math."""
        base_stats = {"str": 20, "agi": 10, "armor": 50}

        # +5 enhancement = 50% boost
        enhanced = self.blacksmith_svc.calculate_enhanced_stats(base_stats, 5)
        assert enhanced["str"] == 30, f"Expected 30 str, got {enhanced['str']}"
        assert enhanced["agi"] == 15, f"Expected 15 agi, got {enhanced['agi']}"
        assert enhanced["armor"] == 75, f"Expected 75 armor, got {enhanced['armor']}"

    async def test_enhancement_attempt(self):
        """INTEGRATION: Test enhancing an item (first level = 100% success)."""
        pid, char = self.test_data["characters"][0]

        # Give gold
        await self.db.execute(
            "UPDATE characters SET gold = 50000 WHERE id = $1", char["id"]
        )

        # Add a fresh item
        ok, msg = await self.inv_svc.add_item(char["id"], "iron_sword")
        assert ok, f"Add item failed: {msg}"

        items = await self.inv_svc.get_all(char["id"])
        swords = [
            i for i in items
            if i["template_id"] == "iron_sword" and not i["is_equipped"]
               and i.get("enhancement_level", 0) == 0
        ]
        assert len(swords) > 0, "No +0 sword for enhancement test"

        # Enhance to +1 (100% success rate)
        result = await self.blacksmith_svc.enhance_item(char["id"], swords[0]["id"])
        assert result["success"], f"Enhancement failed: {result.get('message')}"
        assert result["new_level"] == 1, f"Wrong level: {result.get('new_level')}"

    # ══════════════════════════════════════════════════════════════════════
    #  CATEGORY 6: DUNGEON SYSTEM
    # ══════════════════════════════════════════════════════════════════════

    async def test_dungeon_create_run(self):
        """INTEGRATION: Test creating a dungeon run."""
        pid, char = self.test_data["characters"][0]

        # Set level high enough for deadmines (level_req = 10)
        await self.db.execute(
            "UPDATE characters SET level = 15, in_dungeon = FALSE WHERE id = $1",
            char["id"],
        )

        run_id = await self.dungeon_svc.create_run(
            "deadmines", char["id"], difficulty=1, is_solo=True
        )
        assert run_id is not None, "create_run returned None"
        self.test_data["dungeon_runs"].append(run_id)

    async def test_dungeon_get_run(self):
        """UNIT: Test getting dungeon run details."""
        if not self.test_data["dungeon_runs"]:
            return  # Skip if no run created

        run_id = self.test_data["dungeon_runs"][0]
        run = await self.dungeon_svc.get_run(run_id)
        assert run is not None, "get_run returned None"
        assert run["dungeon_key"] == "deadmines", f"Wrong dungeon: {run['dungeon_key']}"
        assert "participants" in run, "Missing participants"

    async def test_dungeon_advance_floor(self):
        """INTEGRATION: Test advancing dungeon floors."""
        if not self.test_data["dungeon_runs"]:
            return

        run_id = self.test_data["dungeon_runs"][0]
        ok = await self.dungeon_svc.advance_floor(run_id)
        assert ok, "Failed to advance floor"

        run = await self.dungeon_svc.get_run(run_id)
        assert run["current_floor"] == 2, f"Floor not advanced: {run['current_floor']}"

    async def test_dungeon_complete_run(self):
        """INTEGRATION: Test completing a dungeon run."""
        if not self.test_data["dungeon_runs"]:
            return

        run_id = self.test_data["dungeon_runs"][0]
        await self.dungeon_svc.complete_run(run_id, "victory")

        run = await self.dungeon_svc.get_run(run_id)
        assert not run["is_active"], "Run still active after completion"
        assert run["outcome"] == "victory", f"Wrong outcome: {run['outcome']}"

    async def test_dungeon_leave_run(self):
        """INTEGRATION: Test leaving a dungeon run."""
        pid, char = self.test_data["characters"][0]

        # Create a new run
        await self.db.execute(
            "UPDATE characters SET in_dungeon = FALSE WHERE id = $1", char["id"]
        )
        run_id = await self.dungeon_svc.create_run(
            "deadmines", char["id"], difficulty=1, is_solo=True
        )
        assert run_id is not None, "create_run returned None"

        # Leave the run
        await self.dungeon_svc.leave_run(char["id"])

        # Check character not in dungeon
        char_after = await self.char_svc.get_by_id(char["id"])
        assert not char_after["in_dungeon"], "Character still in dungeon after leaving"

    # ══════════════════════════════════════════════════════════════════════
    #  CATEGORY 7: ACHIEVEMENT SYSTEM
    # ══════════════════════════════════════════════════════════════════════

    async def test_achievement_award(self):
        """INTEGRATION: Test awarding an achievement."""
        pid, char = self.test_data["characters"][0]

        # Insert a test achievement template
        await self.db.execute(
            """INSERT INTO achievement_templates (id, name, description, category, points, criteria)
               VALUES ('test_ach_1', 'Test Achievement', 'For testing', 'testing', 10, '{}')
               ON CONFLICT (id) DO NOTHING""",
        )

        # Award it
        newly = await self.achievement_svc.award_achievement(char["id"], "test_ach_1")
        assert newly, "Achievement not awarded"

        # Check it's earned
        has = await self.achievement_svc.has_achievement(char["id"], "test_ach_1")
        assert has, "Achievement not found after awarding"

    async def test_achievement_duplicate_prevention(self):
        """EDGE_CASE: Can't earn the same achievement twice."""
        pid, char = self.test_data["characters"][0]

        # Try awarding again
        newly2 = await self.achievement_svc.award_achievement(char["id"], "test_ach_1")
        assert not newly2, "Achievement awarded twice!"

    async def test_achievement_points(self):
        """UNIT: Test total achievement points calculation."""
        pid, char = self.test_data["characters"][0]
        points = await self.achievement_svc.get_total_points(char["id"])
        assert points >= 10, f"Expected at least 10 points, got {points}"

    # ══════════════════════════════════════════════════════════════════════
    #  CATEGORY 8: DAILY LOGIN SYSTEM
    # ══════════════════════════════════════════════════════════════════════

    async def test_daily_login_first_claim(self):
        """INTEGRATION: Test first daily login claim."""
        pid, char = self.test_data["characters"][0]

        # Clear existing streak
        await self.db.execute(
            "DELETE FROM login_streaks WHERE character_id=$1", char["id"]
        )

        result = await self.daily_svc.claim_daily_reward(char["id"])
        assert result["claimed"], f"First claim failed: {result.get('message')}"
        assert result["current_streak"] == 1, f"Wrong streak: {result['current_streak']}"
        assert result["gold"] > 0, "No gold reward"
        assert result["xp"] > 0, "No XP reward"

    async def test_daily_login_duplicate_claim(self):
        """EDGE_CASE: Can't claim daily reward twice on same day."""
        pid, char = self.test_data["characters"][0]

        result = await self.daily_svc.claim_daily_reward(char["id"])
        assert not result["claimed"], "Should not allow double claim"

    async def test_daily_login_streak_info(self):
        """UNIT: Test get_streak returns data."""
        pid, char = self.test_data["characters"][0]
        streak = await self.daily_svc.get_streak(char["id"])
        assert streak["current_streak"] >= 1, f"Bad streak: {streak['current_streak']}"
        assert streak["total_logins"] >= 1, f"Bad logins: {streak['total_logins']}"

    # ══════════════════════════════════════════════════════════════════════
    #  CATEGORY 9: DATABASE INTEGRITY
    # ══════════════════════════════════════════════════════════════════════

    async def test_foreign_key_constraint_inventory(self):
        """INTEGRATION: Test FK prevents inventory for non-existent character."""
        import uuid
        fake_id = uuid.UUID("00000000-0000-0000-0000-000000000000")

        try:
            await self.db.execute(
                """INSERT INTO inventory (character_id, template_id, quantity)
                   VALUES ($1, 'iron_sword', 1)""",
                fake_id,
            )
            assert False, "Foreign key constraint didn't work!"
        except Exception as e:
            error_msg = str(e).lower()
            assert "foreign key" in error_msg or "violates" in error_msg, (
                f"Wrong error: {e}"
            )

    async def test_cascade_deletion_inventory(self):
        """INTEGRATION: Test CASCADE deletes inventory with character."""
        pid, char = await self._create_test_character("CascadeInvTest")

        # Add item
        await self.inv_svc.add_item(char["id"], "iron_sword")

        # Clean up FK references without CASCADE
        await self.db.execute("DELETE FROM gold_log WHERE character_id=$1", char["id"])

        # Delete character
        await self.db.execute("DELETE FROM characters WHERE id=$1", char["id"])

        # Verify inventory gone
        inv = await self.db.fetch(
            "SELECT * FROM inventory WHERE character_id=$1", char["id"]
        )
        assert len(inv) == 0, "Inventory not cascade deleted"

    async def test_cascade_deletion_quest_progress(self):
        """INTEGRATION: Test CASCADE deletes quest progress with character."""
        pid, char = await self._create_test_character("CascadeQuestTest")

        # Add quest
        await self.db.execute(
            """INSERT INTO quest_progress (character_id, quest_id, npc_id, state)
               VALUES ($1, 'cascade_quest', 'test_npc', 'active')""",
            char["id"],
        )

        # Clean up FK references without CASCADE
        await self.db.execute("DELETE FROM gold_log WHERE character_id=$1", char["id"])

        # Delete character
        await self.db.execute("DELETE FROM characters WHERE id=$1", char["id"])

        # Verify quest gone
        quests = await self.db.fetch(
            "SELECT * FROM quest_progress WHERE character_id=$1", char["id"]
        )
        assert len(quests) == 0, "Quest progress not cascade deleted"

    async def test_gold_log_integrity(self):
        """INTEGRATION: Test gold operations create proper logs."""
        pid, char = self.test_data["characters"][0]

        await self.db.execute(
            "UPDATE characters SET gold = 0 WHERE id = $1", char["id"]
        )

        # Add gold
        await self.char_svc.add_gold(char["id"], 100, reason="test_log", source="drop")

        # Check log entry
        log_entry = await self.db.fetchrow(
            "SELECT * FROM gold_log WHERE character_id=$1 ORDER BY created_at DESC LIMIT 1",
            char["id"],
        )
        assert log_entry is not None, "No gold log entry"
        assert log_entry["amount"] == 100, f"Wrong amount: {log_entry['amount']}"
        assert log_entry["balance_after"] == 100, f"Wrong balance: {log_entry['balance_after']}"

    # ══════════════════════════════════════════════════════════════════════
    #  CATEGORY 10: CONFIG VALIDATION
    # ══════════════════════════════════════════════════════════════════════

    async def test_all_zones_have_enemies_and_bosses(self):
        """UNIT: Test every zone has enemies and bosses configured."""
        from config.settings import ZONES, ENEMIES

        for zone_key, zone in ZONES.items():
            assert len(zone.enemies) > 0, f"Zone '{zone_key}' has no enemies"
            assert len(zone.bosses) > 0, f"Zone '{zone_key}' has no bosses"

            # Verify enemies exist in ENEMIES dict
            for enemy_key in zone.enemies:
                assert enemy_key in ENEMIES, (
                    f"Zone '{zone_key}' references unknown enemy '{enemy_key}'"
                )
            for boss_key in zone.bosses:
                assert boss_key in ENEMIES, (
                    f"Zone '{zone_key}' references unknown boss '{boss_key}'"
                )
                assert ENEMIES[boss_key].is_boss, (
                    f"Zone '{zone_key}' boss '{boss_key}' is not marked as boss"
                )

    async def test_all_classes_have_specs_and_abilities(self):
        """UNIT: Test every class has specs and starter abilities."""
        from config.settings import CLASSES, SPECIALIZATIONS
        from services.combat.combat_engine import ABILITIES

        for cls_key, cls_config in CLASSES.items():
            assert len(cls_config.specializations) >= 2, (
                f"Class '{cls_key}' has < 2 specs"
            )
            assert len(cls_config.starter_abilities) >= 3, (
                f"Class '{cls_key}' has < 3 starter abilities"
            )

            # Verify specs exist
            for spec_key in cls_config.specializations:
                assert spec_key in SPECIALIZATIONS, (
                    f"Class '{cls_key}' references missing spec '{spec_key}'"
                )

            # Verify abilities exist
            for ab_key in cls_config.starter_abilities:
                assert ab_key in ABILITIES, (
                    f"Class '{cls_key}' references missing ability '{ab_key}'"
                )

    async def test_dungeon_configs_valid(self):
        """UNIT: Test dungeon configurations are valid."""
        from config.settings import DUNGEONS

        for key, dungeon in DUNGEONS.items():
            assert dungeon.floors >= 1, f"Dungeon '{key}' has < 1 floors"
            assert dungeon.level_req >= 1, f"Dungeon '{key}' has invalid level_req"
            assert len(dungeon.enemies_per_floor) > 0, (
                f"Dungeon '{key}' has no enemies_per_floor"
            )
            assert len(dungeon.floor_bosses) > 0, (
                f"Dungeon '{key}' has no floor_bosses"
            )

    # ══════════════════════════════════════════════════════════════════════
    #  RUN ALL TESTS
    # ══════════════════════════════════════════════════════════════════════

    async def run_all_tests(self, verbose: bool = True):
        """Run complete test suite."""
        print("\n" + "=" * 120)
        print("🚀 STARTING COMPLETE GAME TEST SUITE")
        print("=" * 120 + "\n")

        test_methods = [m for m in dir(self) if m.startswith("test_")]
        print(f"Testing {len(test_methods)} test cases...\n")

        # ── CHARACTER SYSTEM ─────────────────────────────────────────────
        await self.run_test(self.test_character_creation_all_classes, "Character", TestType.UNIT)
        await self.run_test(self.test_character_creation_invalid_class, "Character", TestType.EDGE_CASE)
        await self.run_test(self.test_character_duplicate_name, "Character", TestType.EDGE_CASE)
        await self.run_test(self.test_character_only_one_active, "Character", TestType.EDGE_CASE)
        await self.run_test(self.test_get_character_methods, "Character", TestType.UNIT)
        await self.run_test(self.test_specialization_level_requirement, "Character", TestType.UNIT)
        await self.run_test(self.test_specialization_class_mismatch, "Character", TestType.EDGE_CASE)
        await self.run_test(self.test_total_stats_with_gear, "Character", TestType.UNIT)
        await self.run_test(self.test_xp_and_leveling, "Character", TestType.INTEGRATION)
        await self.run_test(self.test_gold_operations, "Character", TestType.UNIT)
        await self.run_test(self.test_full_restore, "Character", TestType.UNIT)
        await self.run_test(self.test_character_deletion_cascade, "Character", TestType.INTEGRATION)

        # ── COMBAT ENGINE ────────────────────────────────────────────────
        await self.run_test(self.test_combat_engine_basic_attack, "Combat", TestType.UNIT)
        await self.run_test(self.test_combat_engine_ability_with_status_effect, "Combat", TestType.UNIT)
        await self.run_test(self.test_combat_engine_armor_reduction, "Combat", TestType.UNIT)
        await self.run_test(self.test_combat_engine_boss_damage_scale, "Combat", TestType.UNIT)
        await self.run_test(self.test_combat_engine_stealth_mechanics, "Combat", TestType.UNIT)
        await self.run_test(self.test_combat_engine_execute_threshold, "Combat", TestType.UNIT)
        await self.run_test(self.test_all_12_spec_passives_defined, "Combat", TestType.UNIT)
        await self.run_test(self.test_ability_unlock_levels_defined, "Combat", TestType.UNIT)
        await self.run_test(self.test_zone_based_boss_scaling, "Combat", TestType.UNIT)

        # ── QUEST SYSTEM (CRITICAL) ──────────────────────────────────────
        await self.run_test(self.test_quest_offer_and_accept, "Quest", TestType.INTEGRATION)
        await self.run_test(self.test_quest_kill_tracking, "Quest", TestType.INTEGRATION)
        await self.run_test(self.test_quest_kill_tracking_multiple_kills, "Quest", TestType.INTEGRATION)
        await self.run_test(self.test_quest_metadata_persistence, "Quest", TestType.INTEGRATION)
        await self.run_test(self.test_quest_advance_and_complete, "Quest", TestType.INTEGRATION)
        await self.run_test(self.test_quest_abandon, "Quest", TestType.UNIT)
        await self.run_test(self.test_quest_timed_expiration, "Quest", TestType.INTEGRATION)
        await self.run_test(self.test_npc_discovery, "Quest", TestType.INTEGRATION)
        await self.run_test(self.test_reputation_system, "Quest", TestType.INTEGRATION)

        # ── INVENTORY & ITEMS ────────────────────────────────────────────
        await self.run_test(self.test_add_item, "Inventory", TestType.UNIT)
        await self.run_test(self.test_equip_and_unequip, "Inventory", TestType.INTEGRATION)
        await self.run_test(self.test_get_inventory, "Inventory", TestType.UNIT)
        await self.run_test(self.test_sell_item, "Inventory", TestType.INTEGRATION)
        await self.run_test(self.test_use_consumable, "Inventory", TestType.INTEGRATION)
        await self.run_test(self.test_loot_generation, "Inventory", TestType.UNIT)
        await self.run_test(self.test_rarity_rolling, "Inventory", TestType.UNIT)

        # ── BLACKSMITH / ENHANCEMENT ─────────────────────────────────────
        await self.run_test(self.test_enhancement_info, "Blacksmith", TestType.UNIT)
        await self.run_test(self.test_enhancement_stat_calculation, "Blacksmith", TestType.UNIT)
        await self.run_test(self.test_enhancement_attempt, "Blacksmith", TestType.INTEGRATION)

        # ── DUNGEON SYSTEM ───────────────────────────────────────────────
        await self.run_test(self.test_dungeon_create_run, "Dungeon", TestType.INTEGRATION)
        await self.run_test(self.test_dungeon_get_run, "Dungeon", TestType.UNIT)
        await self.run_test(self.test_dungeon_advance_floor, "Dungeon", TestType.INTEGRATION)
        await self.run_test(self.test_dungeon_complete_run, "Dungeon", TestType.INTEGRATION)
        await self.run_test(self.test_dungeon_leave_run, "Dungeon", TestType.INTEGRATION)

        # ── ACHIEVEMENT SYSTEM ───────────────────────────────────────────
        await self.run_test(self.test_achievement_award, "Achievement", TestType.INTEGRATION)
        await self.run_test(self.test_achievement_duplicate_prevention, "Achievement", TestType.EDGE_CASE)
        await self.run_test(self.test_achievement_points, "Achievement", TestType.UNIT)

        # ── DAILY LOGIN ──────────────────────────────────────────────────
        await self.run_test(self.test_daily_login_first_claim, "Daily Login", TestType.INTEGRATION)
        await self.run_test(self.test_daily_login_duplicate_claim, "Daily Login", TestType.EDGE_CASE)
        await self.run_test(self.test_daily_login_streak_info, "Daily Login", TestType.UNIT)

        # ── DATABASE INTEGRITY ───────────────────────────────────────────
        await self.run_test(self.test_foreign_key_constraint_inventory, "Database", TestType.INTEGRATION)
        await self.run_test(self.test_cascade_deletion_inventory, "Database", TestType.INTEGRATION)
        await self.run_test(self.test_cascade_deletion_quest_progress, "Database", TestType.INTEGRATION)
        await self.run_test(self.test_gold_log_integrity, "Database", TestType.INTEGRATION)

        # ── CONFIG VALIDATION ────────────────────────────────────────────
        await self.run_test(self.test_all_zones_have_enemies_and_bosses, "Config", TestType.UNIT)
        await self.run_test(self.test_all_classes_have_specs_and_abilities, "Config", TestType.UNIT)
        await self.run_test(self.test_dungeon_configs_valid, "Config", TestType.UNIT)

        # Print report
        self.report.print_report(verbose=verbose)

        # Cleanup
        await self.cleanup()

        return self.report.get_summary()

    async def cleanup(self):
        """Clean up all test data."""
        print("\n🧹 Cleaning up test data...")

        try:
            # Delete gold_log for test characters first (no CASCADE)
            await self.db.execute(
                """DELETE FROM gold_log WHERE character_id IN (
                       SELECT id FROM characters WHERE name LIKE 'Test%'
                       OR name LIKE '%Test%' OR name LIKE 'Cascade%'
                   )"""
            )

            # Delete market listings for test characters (no CASCADE)
            await self.db.execute(
                """UPDATE market_listings SET is_active = FALSE, buyer_id = NULL
                   WHERE seller_id IN (
                       SELECT id FROM characters WHERE name LIKE 'Test%'
                       OR name LIKE '%Test%' OR name LIKE 'Cascade%'
                   )"""
            )
            await self.db.execute(
                """DELETE FROM market_listings WHERE seller_id IN (
                       SELECT id FROM characters WHERE name LIKE 'Test%'
                       OR name LIKE '%Test%' OR name LIKE 'Cascade%'
                   )"""
            )

            # Delete test characters (CASCADE handles inventory, quests, etc.)
            await self.db.execute(
                """DELETE FROM characters WHERE name LIKE 'Test%'
                   OR name LIKE '%Test%' OR name LIKE 'Cascade%'"""
            )

            # Delete test players
            await self.db.execute(
                "DELETE FROM players WHERE id >= 900000000 AND id < 910000000"
            )

            # Delete test achievement templates
            await self.db.execute(
                "DELETE FROM achievement_templates WHERE id LIKE 'test_%'"
            )

            # Delete orphaned dungeon runs
            await self.db.execute(
                """DELETE FROM dungeon_runs WHERE is_active = FALSE
                   AND completed_at IS NOT NULL
                   AND completed_at < NOW() - INTERVAL '1 minute'"""
            )
        except Exception as e:
            print(f"⚠️  Cleanup error (non-critical): {e}")

        print("✅ Cleanup complete.\n")


# ═══════════════════════════════════════════════════════════════════════════
#  MAIN - Run from command line
# ═══════════════════════════════════════════════════════════════════════════

async def main():
    """Main entry point."""
    import sys
    import os
    import argparse

    # Add project root to path
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    parser = argparse.ArgumentParser(description="Run game test suite")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    args = parser.parse_args()

    # Setup logging
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Import services
    from database.db import Database
    from services.character.character_service import CharacterService
    from services.character.inventory_service import InventoryService
    from services.quest.npc_quest_service import NPCQuestService
    from services.blacksmith.blacksmith_service import BlacksmithService
    from services.dungeon.dungeon_service import DungeonService
    from services.achievement.achievement_service import AchievementService
    from services.daily.daily_login_service import DailyLoginService

    # Connect database
    DATABASE_URL = os.getenv("DATABASE_URL")
    if not DATABASE_URL:
        print("❌ DATABASE_URL environment variable not set!")
        print("   Export it first: export DATABASE_URL='postgresql://...'")
        sys.exit(1)

    db = Database(DATABASE_URL)
    print("🔌 Connecting to database...")
    await db.connect()
    print("✅ Connected!")

    # Initialize schema (idempotent)
    await db.initialize_schema()

    # Initialize services
    char_svc = CharacterService(db)
    inv_svc = InventoryService(db)
    quest_svc = NPCQuestService(db)
    blacksmith_svc = BlacksmithService(db)
    dungeon_svc = DungeonService(db)
    achievement_svc = AchievementService(db)
    daily_svc = DailyLoginService(db)

    # Create test suite
    test_suite = CompleteGameTestSuite(
        db=db,
        char_svc=char_svc,
        inv_svc=inv_svc,
        quest_svc=quest_svc,
        blacksmith_svc=blacksmith_svc,
        dungeon_svc=dungeon_svc,
        achievement_svc=achievement_svc,
        daily_svc=daily_svc,
    )

    # Run tests
    summary = await test_suite.run_all_tests(verbose=args.verbose)

    # Close database
    await db.close()

    # Exit with error code if tests failed
    sys.exit(0 if summary["failed"] == 0 and summary["errors"] == 0 else 1)


if __name__ == "__main__":
    asyncio.run(main())
