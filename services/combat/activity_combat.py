"""
Embedded Activity (iframe) combat — HTTP-driven turns, separate from Discord channel combat.

Sessions are keyed by Discord user id. Uses the same CombatEngine / CombatSession as /fight.
"""

from __future__ import annotations

import logging
import random
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from uuid import uuid4

from config.settings import (
    ABILITY_UNLOCK_LEVELS,
    CLASSES,
    ENEMIES,
    RARITIES,
    Settings,
    ZONES,
    _boss_hp_scale_for_zone,
)
from services.combat.combat_engine import ABILITIES, CombatEngine, CombatSession, Combatant

log = logging.getLogger("activity_combat")

# discord_user_id -> in-memory combat (iframe only)
ACTIVE_ACTIVITY: Dict[int, "ActivityCombatState"] = {}


@dataclass
class ActivityCombatState:
    session: CombatSession
    log_lines: List[str] = field(default_factory=list)
    potion_used: bool = False


def _make_enemy(key: str, char_level: int, zone=None) -> Combatant:
    tmpl = ENEMIES.get(key, ENEMIES["kobold"])
    scale = 1 + char_level * 0.06
    hp = int(tmpl.hp_base * scale)
    if tmpl.is_boss:
        boss_scale = _boss_hp_scale_for_zone(zone) if zone is not None else Settings.BOSS_HP_SCALE
        hp = int(hp * boss_scale)
    return Combatant(
        id=str(uuid4()),
        name=f"{tmpl.emoji} {tmpl.name}",
        is_player=False,
        char_id=None,
        current_hp=hp,
        max_hp=hp,
        current_res=0,
        max_res=0,
        res_type="none",
        attack_power=int(tmpl.attack_power * scale),
        dmg_min=int(tmpl.damage_min * scale),
        dmg_max=int(tmpl.damage_max * scale),
        armor=int(tmpl.armor * scale),
        crit_chance=tmpl.crit_chance,
    )


def _make_player(char: dict, stats) -> Combatant:
    cls = CLASSES[char["class"]]
    return Combatant(
        id=str(char["id"]),
        name=char["name"],
        is_player=True,
        char_id=char["id"],
        current_hp=char["current_hp"],
        max_hp=char["max_hp"],
        current_res=char["current_res"],
        max_res=char["max_res"],
        specialization=char.get("specialization"),
        res_type=cls.resource,
        attack_power=stats["attack_power"],
        spell_power=stats["spell_power"],
        dmg_min=stats.get("dmg_min", 8) or 8,
        dmg_max=stats.get("dmg_max", 16) or 16,
        armor=stats["armor"],
        crit_chance=stats["crit_chance"],
        dodge_chance=stats["dodge_chance"],
        haste=stats.get("haste", 0.0),
        lifesteal=stats.get("lifesteal", 0.0),
        resistance=stats.get("resistance", 0),
        hit_rating=stats.get("hit_rating", 0.0),
        class_key=char.get("class"),
    )


def _char_in_discord_channel_combat(char_id) -> bool:
    """True if this character already has an active /fight session in a Discord channel."""
    from cogs.combat.combat_cog import ACTIVE  # lazy: avoids import cycle / discord at module import

    for sess in ACTIVE.values():
        for p in sess.players:
            if not p.is_player or p.char_id is None:
                continue
            if str(p.char_id) == str(char_id):
                return True
    return False


def _clear_activity_session(discord_id: int) -> None:
    ACTIVE_ACTIVITY.pop(discord_id, None)


def _serialize_combatant(c: Combatant) -> Dict[str, Any]:
    return {
        "id": c.id,
        "name": c.name,
        "current_hp": c.current_hp,
        "max_hp": c.max_hp,
        "current_res": c.current_res,
        "max_res": c.max_res,
        "res_type": c.res_type,
    }


def _ability_options(char: dict, player: Combatant) -> List[Dict[str, Any]]:
    cls = CLASSES[char["class"]]
    keys = ["auto_attack"] + list(cls.starter_abilities)
    if char.get("specialization"):
        from config.settings import SPECIALIZATIONS

        spec = SPECIALIZATIONS.get(char["specialization"])
        if spec:
            keys.extend(spec.bonus_abilities)

    cost_mult = getattr(Settings, "RESOURCE_COST_MULT", {}).get(char["class"], 1.0)
    char_level = char.get("level", 1)
    out: List[Dict[str, Any]] = []
    seen = set()
    for key in keys:
        if key in seen:
            continue
        seen.add(key)
        ab = ABILITIES.get(key)
        if not ab:
            continue
        unlock_level = ABILITY_UNLOCK_LEVELS.get(key, 1)
        if char_level < unlock_level:
            continue
        eff_cost = int(ab.cost * cost_mult) if ab.cost else 0
        cd = player.ability_cooldowns.get(key, 0)
        disabled: Optional[str] = None
        if cd:
            disabled = f"Cooldown: {cd}"
        elif ab.cost_type in ("mana", "energy", "rage") and eff_cost and player.current_res < eff_cost:
            disabled = f"Not enough {ab.cost_type}"
        out.append(
            {
                "key": key,
                "name": ab.name,
                "emoji": ab.emoji,
                "description": ab.description[:120],
                "cost_type": ab.cost_type,
                "cost": eff_cost,
                "cooldown": cd,
                "disabled": disabled,
            }
        )
    return out[:30]


def serialize_activity_state(
    ac: ActivityCombatState,
    char: dict,
    *,
    awaiting_action: bool,
    can_potion: bool,
) -> Dict[str, Any]:
    session = ac.session
    player = session.alive_players[0] if session.alive_players else session.players[0]
    enemy = session.alive_enemies[0] if session.alive_enemies else session.enemies[0]
    return {
        "phase": "combat" if awaiting_action and not session.over else "ended",
        "turn": session.turn,
        "player": _serialize_combatant(player),
        "enemy": _serialize_combatant(enemy),
        "log": ac.log_lines[-12:],
        "abilities": _ability_options(char, player),
        "can_potion": can_potion and not ac.potion_used,
        "is_boss": session.is_boss,
        "zone_key": session.zone_key,
        "enemy_key": session.enemy_key,
        # Embedded Activity: multi-slot party UI only while character is in a dungeon run
        "in_dungeon": bool(char.get("in_dungeon")),
    }


async def list_zone_enemies(char: dict) -> List[Dict[str, str]]:
    zone = ZONES.get(char["current_zone"])
    if not zone:
        return []
    out: List[Dict[str, str]] = []
    for key in zone.enemies:
        e = ENEMIES.get(key)
        if e:
            out.append({"key": key, "name": e.name, "emoji": e.emoji, "kind": "enemy"})
    for key in zone.bosses:
        e = ENEMIES.get(key)
        if e:
            out.append({"key": key, "name": e.name, "emoji": e.emoji, "kind": "boss"})
    return out


async def start_activity_combat(
    bot,
    discord_id: int,
    enemy_key: str,
    guild_id: Optional[int],
    *,
    force: bool = False,
) -> Dict[str, Any]:
    """Begin iframe combat or return existing session."""
    db = getattr(bot, "db", None)
    if db is None or db.pool is None:
        return {"error": "database_unavailable"}

    from services.character.character_service import CharacterService
    from services.character.inventory_service import InventoryService

    char_svc = CharacterService(db)
    inv_svc = InventoryService(db)
    char = await char_svc.get_character(discord_id)
    if not char:
        return {"error": "no_character", "message": "Create a character with /character create in Discord."}

    if discord_id in ACTIVE_ACTIVITY:
        if not force:
            ac = ACTIVE_ACTIVITY[discord_id]
            has_potion = await _has_healing_potion(db, char["id"])
            can_potion = bool(has_potion) and not ac.potion_used
            return {
                "error": "already_in_combat",
                "state": serialize_activity_state(ac, char, awaiting_action=True, can_potion=can_potion),
            }
        _clear_activity_session(discord_id)
        await db.execute("UPDATE characters SET combat_status='idle' WHERE id=$1", char["id"])
        char = await char_svc.get_character(discord_id)
        if not char:
            return {"error": "no_character", "message": "Create a character with /character create in Discord."}

    zone = ZONES.get(char["current_zone"])
    if not zone:
        return {"error": "unknown_zone"}
    if char["level"] < zone.level_range[0]:
        return {
            "error": "level_too_low",
            "message": f"This zone requires level {zone.level_range[0]}+.",
        }

    if enemy_key not in zone.enemies and enemy_key not in zone.bosses:
        return {"error": "invalid_enemy", "message": "That enemy is not in your current zone."}

    # Same combat_status rules as /fight (Discord channel sessions)
    if char["combat_status"] == "in_combat":
        if _char_in_discord_channel_combat(char["id"]):
            return {
                "error": "in_discord_combat",
                "message": "Finish your fight in Discord first, or wait for it to end.",
            }
        await db.execute("UPDATE characters SET combat_status='idle' WHERE id=$1", char["id"])
        char = await char_svc.get_character(discord_id)
        if not char:
            return {"error": "no_character", "message": "Create a character with /character create in Discord."}

    stats = await char_svc.total_stats(char["id"])
    player_c = _make_player(dict(char), stats)
    enemy_c = _make_enemy(enemy_key, char["level"], zone)
    is_boss = enemy_key in zone.bosses

    session = CombatSession(
        session_id=uuid4(),
        players=[player_c],
        enemies=[enemy_c],
        is_boss=is_boss,
        enemy_key=enemy_key,
        zone_key=char["current_zone"],
    )

    engine = CombatEngine()
    session.turn = 1
    player = session.alive_players[0]
    log_lines: List[str] = list(engine.tick_turn(player))
    if player.is_dead:
        return {"error": "player_dead_start", "message": "You cannot start combat at 0 HP."}

    await db.execute(
        "UPDATE characters SET combat_status='in_combat', last_combat=NOW(), pending_encounter=NULL WHERE id=$1",
        char["id"],
    )

    ac = ActivityCombatState(session=session, log_lines=log_lines, potion_used=False)
    ACTIVE_ACTIVITY[discord_id] = ac

    has_potion = await _has_healing_potion(db, char["id"])
    can_potion = bool(has_potion)

    return {
        "ok": True,
        "guild_id": guild_id,
        "state": serialize_activity_state(ac, char, awaiting_action=True, can_potion=can_potion),
    }


async def _has_healing_potion(db, char_id) -> Optional[Any]:
    return await db.fetchrow(
        """
        SELECT i.id, t.name, t.effect_value
        FROM inventory i
        JOIN item_templates t ON i.template_id = t.id
        WHERE i.character_id = $1
          AND i.quantity > 0
          AND t.item_type = 'consumable'
          AND t.effect_type = 'heal_hp'
        ORDER BY t.effect_value DESC
        LIMIT 1
        """,
        char_id,
    )


async def process_activity_action(
    bot,
    discord_id: int,
    guild_id: Optional[int],
    body: Dict[str, Any],
) -> Dict[str, Any]:
    """One player action (ability / flee / potion) plus enemy turn when appropriate."""
    db = getattr(bot, "db", None)
    if db is None or db.pool is None:
        return {"error": "database_unavailable"}

    ac = ACTIVE_ACTIVITY.get(discord_id)
    if not ac:
        return {"error": "no_session", "message": "Start a fight from the Combat tab first."}

    from services.character.character_service import CharacterService
    from services.character.inventory_service import InventoryService

    char_svc = CharacterService(db)
    inv_svc = InventoryService(db)
    char = await char_svc.get_character(discord_id)
    if not char:
        _clear_activity_session(discord_id)
        return {"error": "no_character"}

    session = ac.session
    engine = CombatEngine()
    log_lines = ac.log_lines
    char_id = char["id"]

    if session.over:
        _clear_activity_session(discord_id)
        return {"error": "session_over", "message": "Combat already ended — start a new fight."}

    player = session.alive_players[0]
    enemy = session.alive_enemies[0]

    flee = bool(body.get("flee"))
    potion = bool(body.get("potion"))
    ability_key = (body.get("ability") or body.get("ability_key") or "").strip()

    # ── Flee ───────────────────────────────────────────────────────────────
    if flee:
        flee_roll = Settings.FLEE_BASE_CHANCE + player.dodge_chance * 0.01
        if random.random() < flee_roll:
            log_lines.append("🏃 You escaped!")
            await _activity_fled(bot, guild_id, char, player, char_svc, db)
            _clear_activity_session(discord_id)
            return {
                "ok": True,
                "ended": True,
                "outcome": {"type": "flee", "title": "🏃 Escaped!", "lines": ["You fled from combat. HP unchanged."]},
            }
        log_lines.append("🚫 You couldn't flee!")
        session.turn += 1
        ticks = engine.tick_turn(player)
        log_lines.extend(ticks)
        if player.is_dead:
            return await _finish_defeat(bot, guild_id, discord_id, char, player, char_svc, db, log_lines)
        has_potion = await _has_healing_potion(db, char_id)
        can_potion = bool(has_potion) and not ac.potion_used
        fresh = await char_svc.get_character(discord_id)
        return {
            "ok": True,
            "ended": False,
            "state": serialize_activity_state(ac, fresh, awaiting_action=True, can_potion=can_potion),
        }

    # ── Potion ────────────────────────────────────────────────────────────
    if potion:
        has_potion_row = await _has_healing_potion(db, char_id)
        if not has_potion_row:
            log_lines.append("❌ You don't have any healing potions!")
        elif ac.potion_used:
            log_lines.append("❌ You already used a potion this fight.")
        else:
            from uuid import UUID as _UUID

            potion_id = has_potion_row["id"]
            ok, msg_text, effect = await inv_svc.use_consumable(char_id, potion_id)
            healed = 0
            if ok and effect and effect.get("type") == "heal_hp":
                base_val = effect.get("value", 80)
                heal_val = max(base_val, player.max_hp // 4)
                healed = await char_svc.heal(char_id, heal_val)
                player.current_hp = min(player.max_hp, player.current_hp + healed)
                log_lines.append(f"🧪 {msg_text} Restored **{healed}** HP.")
            else:
                log_lines.append(f"🧪 {msg_text}")
            ac.potion_used = ok or ac.potion_used

        session.turn += 1
        ticks = engine.tick_turn(player)
        log_lines.extend(ticks)
        if player.is_dead:
            return await _finish_defeat(bot, guild_id, discord_id, char, player, char_svc, db, log_lines)
        has_potion = await _has_healing_potion(db, char_id)
        can_potion = bool(has_potion) and not ac.potion_used
        fresh = await char_svc.get_character(discord_id)
        return {
            "ok": True,
            "ended": False,
            "state": serialize_activity_state(ac, fresh, awaiting_action=True, can_potion=can_potion),
        }

    # ── Ability ───────────────────────────────────────────────────────────
    if not ability_key:
        ability_key = "auto_attack"

    ab = ABILITIES.get(ability_key)
    if not ab:
        ability_key = "auto_attack"
        ab = ABILITIES.get("auto_attack", ABILITIES["auto_attack"])

    cls = CLASSES[char["class"]]
    cost_mult = getattr(Settings, "RESOURCE_COST_MULT", {}).get(char["class"], 1.0)
    eff_cost = int(ab.cost * cost_mult) if ab.cost else 0

    if ab.cost_type in ("mana", "energy", "rage") and player.current_res < eff_cost:
        log_lines.append(f"❌ Not enough {ab.cost_type} for **{ab.name}**!")
    elif ability_key in player.ability_cooldowns:
        log_lines.append(f"⏳ **{ab.name}** is on cooldown!")
    else:
        if ab.cost_type in ("mana", "energy", "rage") and eff_cost:
            player.current_res = max(0, player.current_res - eff_cost)
        try:
            results = engine.use_ability(ability_key, player, [enemy], session=session)
            for r in results:
                log_lines.append(r.narrative)
            session.log.extend(results)
        except Exception as e:
            log.exception("activity combat ability error")
            log_lines.append(f"⚠️ **{ab.name}** failed: {str(e)[:80]}")
            try:
                results = engine.use_ability("auto_attack", player, [enemy], session=session)
                for r in results:
                    log_lines.append(r.narrative)
                session.log.extend(results)
            except Exception as e2:
                log.exception("activity auto_attack fallback failed: %s", e2)

    if session.over and session.players_won:
        return await _finish_victory(bot, guild_id, discord_id, char, session, player, char_svc, inv_svc, engine, db, log_lines)

    if session.over:
        return await _finish_defeat(bot, guild_id, discord_id, char, player, char_svc, db, log_lines)

    # Enemy phase (same as Discord /fight)
    e_ticks = engine.tick_turn(enemy)
    if e_ticks:
        log_lines.extend(e_ticks)

    if not enemy.is_dead:
        if session.is_boss:
            session.boss_phase = engine.boss_phase(enemy)
        e_ab, e_targets = engine.enemy_turn(enemy, session.alive_players, session.is_boss, session.boss_phase)
        if e_targets:
            e_results = engine.use_ability(e_ab, enemy, e_targets, session=session)
            for r in e_results:
                log_lines.append(r.narrative)
            session.log.extend(e_results)

    if session.over:
        if session.players_won:
            return await _finish_victory(bot, guild_id, discord_id, char, session, player, char_svc, inv_svc, engine, db, log_lines)
        return await _finish_defeat(bot, guild_id, discord_id, char, player, char_svc, db, log_lines)

    session.turn += 1
    fresh = await char_svc.get_character(discord_id)
    player2 = session.alive_players[0]
    ticks2 = engine.tick_turn(player2)
    log_lines.extend(ticks2)
    if player2.is_dead:
        return await _finish_defeat(bot, guild_id, discord_id, char, player2, char_svc, db, log_lines)

    has_potion = await _has_healing_potion(db, char_id)
    can_potion = bool(has_potion) and not ac.potion_used
    return {
        "ok": True,
        "ended": False,
        "state": serialize_activity_state(ac, fresh, awaiting_action=True, can_potion=can_potion),
    }


async def _finish_defeat(
    bot,
    guild_id: Optional[int],
    discord_id: int,
    char: dict,
    player: Combatant,
    char_svc,
    db,
    log_lines: List[str],
) -> Dict[str, Any]:
    revive_hp = max(1, char["max_hp"] // 5)
    await db.execute(
        "UPDATE characters SET current_hp=$2, combat_status='idle' WHERE id=$1",
        char["id"],
        revive_hp,
    )
    _clear_activity_session(discord_id)
    lines = log_lines[-8:] + ["💀 You were defeated — you revive with 20% HP."]
    return {
        "ok": True,
        "ended": True,
        "outcome": {
            "type": "defeat",
            "title": "💀 Defeated",
            "lines": lines,
        },
    }


async def _activity_fled(bot, guild_id, char, player, char_svc, db) -> None:
    await char_svc.sync_combat_hp(char["id"], player.current_hp, player.current_res)
    await db.execute("UPDATE characters SET combat_status='idle' WHERE id=$1", char["id"])


async def _finish_victory(
    bot,
    guild_id: Optional[int],
    discord_id: int,
    char: dict,
    session: CombatSession,
    player: Combatant,
    char_svc,
    inv_svc,
    engine: CombatEngine,
    db,
    log_lines: List[str],
) -> Dict[str, Any]:
    from services.achievement.achievement_service import AchievementService
    from services.quest.npc_quest_service import NPCQuestService

    from services.reward_multipliers import get_combined_reward_multipliers

    xp_mult, gold_mult, _boss_add = await get_combined_reward_multipliers(db, guild_id)

    rewards = engine.calculate_rewards(session, xp_mult, gold_mult)
    xp_result = await char_svc.award_xp(char["id"], rewards["xp"], xp_mult)
    await char_svc.add_gold(char["id"], rewards["gold"], "combat drop")
    await char_svc.sync_combat_hp(char["id"], player.current_hp, player.current_res)

    loot_lines: List[str] = []
    for _ in range(rewards["loot_rolls"]):
        loot = await inv_svc.generate_loot(char["current_zone"], char["level"], session.is_boss)
        if loot:
            ok, _ = await inv_svc.add_item(
                char["id"], loot["template"]["id"], loot["rarity"], bonus=loot["bonus"]
            )
            if ok:
                rc = RARITIES[loot["rarity"]]
                loot_lines.append(f"{rc.emoji} **{loot['template']['name']}** [{loot['rarity'].title()}]")

    potion_chance = 0.35 if session.is_boss else 0.25
    if random.random() < potion_chance:
        ok, _ = await inv_svc.add_item(char["id"], "health_potion", "common", from_="combat_drop")
        if ok:
            loot_lines.append("🧪 **Health Potion** (refill)")

    try:
        ach_svc = AchievementService(db)
        newly_earned = await ach_svc.check_and_award(char["id"], "kill", {"is_boss": session.is_boss})
        for ach_id in newly_earned or []:
            ach = await ach_svc.get_achievement(ach_id)
            if ach:
                loot_lines.append(f"🏆 **Achievement:** {ach.get('icon', '🏆')} {ach['name']}!")
    except Exception:
        pass

    quest_lines: List[str] = []
    try:
        quest_svc = NPCQuestService(db)
        quest_notes = await quest_svc.check_kill_progress(
            char["id"], session.enemy_key, session.zone_key, session.is_boss
        )
        quest_lines.extend(quest_notes)
    except Exception as e:
        log.error("Quest progress failed: %s", e)

    await db.execute("UPDATE characters SET combat_status='idle' WHERE id=$1", char["id"])
    _clear_activity_session(discord_id)

    summary = [
        f"+{rewards['xp']:,} XP",
        f"+{rewards['gold']:,} 🪙",
    ]
    if xp_result.get("leveled_up"):
        summary.append(f"LEVEL UP: {xp_result['old_level']} → {xp_result['new_level']}")

    out_lines = log_lines[-6:] + ["🏆 **Victory!**", *summary]
    if loot_lines:
        out_lines.append("📦 " + " · ".join(loot_lines[:6]))
    if quest_lines:
        out_lines.extend(quest_lines[:4])

    # Milestones (non-blocking)
    if guild_id:
        try:
            from services.milestones.milestone_service import MilestoneService

            ms = MilestoneService(db)
            completed = []
            completed.extend(
                await ms.increment(
                    guild_id,
                    "kills_total",
                    1,
                    source="combat_kill",
                    actor_id=discord_id,
                )
            )
            if session.is_boss:
                completed.extend(
                    await ms.increment(
                        guild_id,
                        "boss_kills",
                        1,
                        source="combat_boss_kill",
                        actor_id=discord_id,
                    )
                )
            if rewards.get("gold", 0) > 0:
                completed.extend(
                    await ms.increment(
                        guild_id,
                        "gold_earned",
                        int(rewards["gold"]),
                        source="combat_gold",
                        actor_id=discord_id,
                    )
                )
            if xp_result.get("levels_gained", 0) > 0:
                completed.extend(
                    await ms.increment(
                        guild_id,
                        "levels_gained",
                        int(xp_result["levels_gained"]),
                        source="level_up",
                        actor_id=discord_id,
                    )
                )
            if completed:
                await ms.announce_completions(bot, guild_id, completed)
        except Exception:
            pass

    return {
        "ok": True,
        "ended": True,
        "outcome": {
            "type": "victory",
            "title": "🏆 Victory!",
            "lines": out_lines,
            "xp": rewards["xp"],
            "gold": rewards["gold"],
            "leveled_up": xp_result.get("leveled_up", False),
            "loot": loot_lines,
        },
    }


async def get_activity_combat_state(bot, discord_id: int) -> Dict[str, Any]:
    ac = ACTIVE_ACTIVITY.get(discord_id)
    if not ac:
        return {"active": False}

    from services.character.character_service import CharacterService

    db = getattr(bot, "db", None)
    if db is None or db.pool is None:
        return {"active": False}

    char_svc = CharacterService(db)
    char = await char_svc.get_character(discord_id)
    if not char:
        _clear_activity_session(discord_id)
        return {"active": False}

    has_potion = await _has_healing_potion(db, char["id"])
    can_potion = bool(has_potion) and not ac.potion_used
    return {
        "active": True,
        "state": serialize_activity_state(ac, char, awaiting_action=True, can_potion=can_potion),
    }
