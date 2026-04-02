"""
Embedded Activity (iframe) combat — HTTP-driven turns, separate from Discord channel combat.

Sessions are keyed by Discord user id. Uses the same CombatEngine / CombatSession as /fight.
"""

from __future__ import annotations

import asyncio
import logging
import random
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from config.settings import (
    ABILITY_UNLOCK_LEVELS,
    CLASSES,
    DUNGEONS,
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

# Shared party dungeon (1 CombatSession per run_id; all party members read/write the same fight)
PARTY_DUNGEON_SESSIONS: Dict[UUID, "ActivityCombatState"] = {}
DISCORD_TO_PARTY_RUN: Dict[int, UUID] = {}
# One-shot outcome delivery for party members who did not POST the final action (GET /combat/state consumes).
PARTY_PENDING_OUTCOME: Dict[int, Dict[str, Any]] = {}

# Serialize combat actions per user so rapid parallel requests cannot stack extra turns.
_ACTIVITY_ACTION_LOCKS: Dict[int, asyncio.Lock] = {}
_PARTY_ACTION_LOCKS: Dict[UUID, asyncio.Lock] = {}


def _activity_action_lock(discord_id: int) -> asyncio.Lock:
    lock = _ACTIVITY_ACTION_LOCKS.get(discord_id)
    if lock is None:
        lock = asyncio.Lock()
        _ACTIVITY_ACTION_LOCKS[discord_id] = lock
    return lock


def _party_action_lock(run_id: UUID) -> asyncio.Lock:
    lock = _PARTY_ACTION_LOCKS.get(run_id)
    if lock is None:
        lock = asyncio.Lock()
        _PARTY_ACTION_LOCKS[run_id] = lock
    return lock


@dataclass
class ActivityCombatState:
    session: CombatSession
    log_lines: List[str] = field(default_factory=list)
    potion_used: bool = False
    dungeon_key: Optional[str] = None
    dungeon_floor: Optional[int] = None
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    hp_start: int = 0
    # Party dungeon (shared session)
    party_run_id: Optional[UUID] = None
    party_discord_order: List[int] = field(default_factory=list)
    party_char_to_discord: Dict[str, int] = field(default_factory=dict)
    party_turn_idx: int = 0
    potion_by_discord: Dict[int, bool] = field(default_factory=dict)


def _clear_party_dungeon_session(ac: ActivityCombatState) -> None:
    rid = ac.party_run_id
    if rid is None:
        return
    PARTY_DUNGEON_SESSIONS.pop(rid, None)
    for did in ac.party_discord_order:
        DISCORD_TO_PARTY_RUN.pop(did, None)


def _find_player_for_discord(ac: ActivityCombatState, session: CombatSession, discord_id: int) -> Optional[Combatant]:
    for p in session.players:
        if not p.is_player or p.char_id is None:
            continue
        if ac.party_char_to_discord.get(str(p.char_id)) == discord_id:
            return p
    return None


def _alive_party_discord_order(ac: ActivityCombatState) -> List[int]:
    session = ac.session
    out: List[int] = []
    for did in ac.party_discord_order:
        p = _find_player_for_discord(ac, session, did)
        if p and not p.is_dead:
            out.append(did)
    return out


def _make_enemy(key: str, char_level: int, zone=None, party_size: int = 1) -> Combatant:
    tmpl = ENEMIES.get(key, ENEMIES["kobold"])
    scale = 1 + char_level * 0.06
    hp = int(tmpl.hp_base * scale)
    if tmpl.is_boss:
        boss_scale = _boss_hp_scale_for_zone(zone) if zone is not None else Settings.BOSS_HP_SCALE
        hp = int(hp * boss_scale)
    if party_size > 1:
        hp = int(hp * (1.0 + 0.35 * (party_size - 1)))
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
    from services.character.character_service import CharacterService

    char = CharacterService.normalize_resources(dict(char))
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


def clear_activity_combat_session(discord_id: int) -> None:
    """Drop iframe combat session (e.g. after /rest from Activity). Solo only — use dissolve_party_dungeon_combat_for_user for party."""
    _clear_activity_session(discord_id)


async def dissolve_party_dungeon_combat_for_user(bot, discord_id: int) -> None:
    """Clear shared party dungeon combat for all members (e.g. when one player rests)."""
    run_id = DISCORD_TO_PARTY_RUN.get(discord_id)
    if run_id is None:
        return
    ac = PARTY_DUNGEON_SESSIONS.get(run_id)
    if not ac:
        DISCORD_TO_PARTY_RUN.pop(discord_id, None)
        return
    db = getattr(bot, "db", None)
    if db and db.pool:
        for did in ac.party_discord_order:
            await db.execute("UPDATE characters SET combat_status='idle' WHERE player_id=$1", did)
            PARTY_PENDING_OUTCOME.pop(did, None)
    _clear_party_dungeon_session(ac)


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


def _dungeon_total_floors_payload(ac: ActivityCombatState) -> Optional[int]:
    """Total floors for the dungeon encounter (Activity UI); avoids client guessing from current floor."""
    if not ac.dungeon_key:
        return None
    cfg = DUNGEONS.get(ac.dungeon_key)
    return int(cfg.floors) if cfg else None


def serialize_activity_state(
    ac: ActivityCombatState,
    char: dict,
    *,
    awaiting_action: bool,
    can_potion: bool,
    viewer_discord_id: Optional[int] = None,
) -> Dict[str, Any]:
    session = ac.session
    viewer_did = viewer_discord_id if viewer_discord_id is not None else int(char.get("player_id") or 0)

    if ac.party_run_id:
        enemy = session.alive_enemies[0] if session.alive_enemies else session.enemies[0]
        viewer_player = _find_player_for_discord(ac, session, viewer_did)
        if not viewer_player:
            viewer_player = session.alive_players[0] if session.alive_players else session.players[0]
        player_payload = _serialize_combatant(viewer_player)
        player_payload["class"] = char.get("class")
        player_payload["specialization"] = char.get("specialization")

        alive_order = _alive_party_discord_order(ac)
        active_did: Optional[int] = None
        if alive_order and not session.over:
            if ac.party_turn_idx < len(alive_order):
                active_did = alive_order[ac.party_turn_idx]
            else:
                active_did = alive_order[0]

        your_turn = bool(
            active_did is not None
            and active_did == viewer_did
            and awaiting_action
            and not session.over
        )

        party_rows: List[Dict[str, Any]] = []
        for did in ac.party_discord_order:
            p = _find_player_for_discord(ac, session, did)
            if not p:
                continue
            row = _serialize_combatant(p)
            if did == viewer_did:
                row["class"] = char.get("class")
                row["specialization"] = char.get("specialization")
            else:
                row["class"] = p.class_key
                row["specialization"] = p.specialization
            row["your_turn"] = bool(active_did == did and awaiting_action and not session.over)
            party_rows.append(row)

        ab_list: List[Dict[str, Any]] = []
        if your_turn:
            ab_list = _ability_options(char, viewer_player)
        pot_ok = bool(can_potion) and not ac.potion_by_discord.get(viewer_did, False)

        return {
            "phase": "combat" if awaiting_action and not session.over else "ended",
            "turn": session.turn,
            "player": player_payload,
            "enemy": _serialize_combatant(enemy),
            "log": ac.log_lines[-12:],
            "abilities": ab_list,
            "can_potion": pot_ok and your_turn,
            "is_boss": session.is_boss,
            "zone_key": session.zone_key,
            "enemy_key": session.enemy_key,
            "in_dungeon": bool(char.get("in_dungeon")) or bool(ac.dungeon_key),
            "dungeon_key": ac.dungeon_key,
            "dungeon_floor": ac.dungeon_floor,
            "dungeon_total_floors": _dungeon_total_floors_payload(ac),
            "party_mode": True,
            "your_turn": your_turn,
            "active_turn_discord_id": str(active_did) if active_did is not None else None,
            "party_players": party_rows,
        }

    player = session.alive_players[0] if session.alive_players else session.players[0]
    enemy = session.alive_enemies[0] if session.alive_enemies else session.enemies[0]
    player_payload = _serialize_combatant(player)
    # Activity UI loads class/spec icons from `/classes` + `/specs`; include keys here so
    # the client does not depend on inventory fetch timing (player name already comes from state).
    player_payload["class"] = char.get("class")
    player_payload["specialization"] = char.get("specialization")
    return {
        "phase": "combat" if awaiting_action and not session.over else "ended",
        "turn": session.turn,
        "player": player_payload,
        "enemy": _serialize_combatant(enemy),
        "log": ac.log_lines[-12:],
        "abilities": _ability_options(char, player),
        "can_potion": can_potion and not ac.potion_used,
        "is_boss": session.is_boss,
        "zone_key": session.zone_key,
        "enemy_key": session.enemy_key,
        # Embedded Activity: multi-slot party UI only while character is in a dungeon run
        "in_dungeon": bool(char.get("in_dungeon")) or bool(ac.dungeon_key),
        "dungeon_key": ac.dungeon_key,
        "dungeon_floor": ac.dungeon_floor,
        "dungeon_total_floors": _dungeon_total_floors_payload(ac),
    }


def _enemy_key_for_dungeon_floor(cfg, floor: int) -> tuple[str, bool]:
    """Resolve enemy for a dungeon floor (matches cogs/dungeon/dungeon_cog)."""
    if floor < 1 or floor > cfg.floors:
        raise ValueError("invalid_floor")
    is_boss = floor == cfg.floors
    if is_boss:
        enemy_key = cfg.floor_bosses[-1]
    else:
        enemy_key = cfg.enemies_per_floor[(floor - 1) % len(cfg.enemies_per_floor)]
    return enemy_key, is_boss


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
    guild_id: Optional[int],
    *,
    force: bool = False,
    enemy_key: Optional[str] = None,
    dungeon_key: Optional[str] = None,
    dungeon_floor: Optional[int] = None,
) -> Dict[str, Any]:
    """Begin iframe combat or return existing session.

    Overworld: pass ``enemy_key`` from the character's current zone.

    Dungeon (Activity tab): pass ``dungeon_key`` + ``dungeon_floor`` (1-based); enemy is resolved
    from ``config.settings.DUNGEONS`` like Discord ``/dungeon`` fights.
    """
    db = getattr(bot, "db", None)
    if db is None or db.pool is None:
        return {"error": "database_unavailable"}

    from services.character.character_service import CharacterService

    char_svc = CharacterService(db)
    char = await char_svc.get_character(discord_id)
    if not char:
        return {"error": "no_character", "message": "Create a character with /character create in Discord."}

    if discord_id in DISCORD_TO_PARTY_RUN:
        pr = DISCORD_TO_PARTY_RUN[discord_id]
        pac = PARTY_DUNGEON_SESSIONS.get(pr)
        if pac and not pac.session.over:
            has_potion = await _has_healing_potion(db, char["id"])
            can_potion = bool(has_potion) and not pac.potion_by_discord.get(discord_id, False)
            return {
                "error": "already_in_combat",
                "state": serialize_activity_state(pac, dict(char), awaiting_action=True, can_potion=can_potion),
            }
        DISCORD_TO_PARTY_RUN.pop(discord_id, None)

    dungeon_mode = bool(dungeon_key and dungeon_floor is not None)
    if not dungeon_mode and not (enemy_key or "").strip():
        return {"error": "missing_enemy_key", "message": "Missing enemy_key or dungeon_key/floor."}

    resolved_dungeon_key: Optional[str] = None
    resolved_dungeon_floor: Optional[int] = None
    zone = ZONES.get(char["current_zone"])
    is_boss: bool

    if dungeon_mode:
        cfg = DUNGEONS.get(dungeon_key or "")
        if not cfg:
            return {"error": "invalid_dungeon", "message": "Unknown dungeon."}
        if char["level"] < cfg.level_req:
            return {
                "error": "level_too_low",
                "message": f"This dungeon requires level {cfg.level_req}+.",
            }
        try:
            enemy_key, is_boss = _enemy_key_for_dungeon_floor(cfg, int(dungeon_floor))
        except (ValueError, TypeError):
            return {"error": "invalid_floor", "message": "Invalid dungeon floor."}
        resolved_dungeon_key = (dungeon_key or "").strip() or None
        resolved_dungeon_floor = int(dungeon_floor)
        if not zone:
            return {"error": "unknown_zone", "message": "Travel to a valid zone first."}

        # Party (2+): /api/game/combat/start must NOT create a separate solo dungeon — only
        # POST /dungeon/party/enter (leader) creates the shared PARTY_DUNGEON_SESSIONS fight.
        from services.dungeon.dungeon_service import DungeonService

        ds = DungeonService(db)
        active_run = await ds.get_active_run(char["id"])
        party_n = len((active_run or {}).get("participants") or [])
        if party_n >= 2:
            return {
                "error": "party_dungeon_use_enter",
                "message": "Party mode (2+): do not start dungeon combat from the Combat tab or Fight floor. "
                "The leader must use Enter Dungeon on the Dungeon tab; other members join the same fight automatically.",
            }
    else:
        enemy_key = (enemy_key or "").strip()
        if not zone:
            return {"error": "unknown_zone"}
        if char["level"] < zone.level_range[0]:
            return {
                "error": "level_too_low",
                "message": f"This zone requires level {zone.level_range[0]}+.",
            }

        if enemy_key not in zone.enemies and enemy_key not in zone.bosses:
            return {"error": "invalid_enemy", "message": "That enemy is not in your current zone."}
        is_boss = enemy_key in zone.bosses

    # Resume only the *same* Activity fight; otherwise clear (e.g. Overworld → Dungeon tab).
    if discord_id in ACTIVE_ACTIVITY:
        ac = ACTIVE_ACTIVITY[discord_id]
        if force:
            _clear_activity_session(discord_id)
            await db.execute("UPDATE characters SET combat_status='idle' WHERE id=$1", char["id"])
            char = await char_svc.get_character(discord_id)
            if not char:
                return {"error": "no_character", "message": "Create a character with /character create in Discord."}
        elif ac.session.over:
            _clear_activity_session(discord_id)
            await db.execute("UPDATE characters SET combat_status='idle' WHERE id=$1", char["id"])
            char = await char_svc.get_character(discord_id)
            if not char:
                return {"error": "no_character", "message": "Create a character with /character create in Discord."}
        else:
            ex_dungeon = ac.dungeon_key
            new_dungeon = resolved_dungeon_key
            same_fight = False
            if ex_dungeon is None and new_dungeon is None:
                same_fight = ac.session.enemy_key == enemy_key
            elif ex_dungeon and new_dungeon:
                same_fight = (
                    ex_dungeon == new_dungeon
                    and ac.dungeon_floor is not None
                    and resolved_dungeon_floor is not None
                    and int(ac.dungeon_floor) == int(resolved_dungeon_floor)
                )
            if same_fight:
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
    if dungeon_mode:
        enemy_c = _make_enemy(enemy_key, char["level"], None)
    else:
        enemy_c = _make_enemy(enemy_key, char["level"], zone)

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

    ac = ActivityCombatState(
        session=session,
        log_lines=log_lines,
        potion_used=False,
        dungeon_key=resolved_dungeon_key,
        dungeon_floor=resolved_dungeon_floor,
        started_at=datetime.now(timezone.utc),
        hp_start=player_c.current_hp,
    )
    ACTIVE_ACTIVITY[discord_id] = ac

    has_potion = await _has_healing_potion(db, char["id"])
    can_potion = bool(has_potion)

    return {
        "ok": True,
        "guild_id": guild_id,
        "state": serialize_activity_state(ac, char, awaiting_action=True, can_potion=can_potion),
    }


async def start_party_dungeon_combat(
    bot,
    run_id: UUID,
    guild_id: Optional[int],
    leader_discord_id: int,
) -> Dict[str, Any]:
    """One shared CombatSession for the whole party (2+ players). Leader only."""
    db = getattr(bot, "db", None)
    if db is None or db.pool is None:
        return {"error": "database_unavailable"}

    from services.character.character_service import CharacterService
    from services.dungeon.dungeon_service import DungeonService

    char_svc = CharacterService(db)
    dungeon_svc = DungeonService(db)

    run = await dungeon_svc.get_run(run_id)
    if not run or not run.get("is_active"):
        return {"error": "invalid_run", "message": "Dungeon run not found or inactive."}

    participants = run.get("participants") or []
    if len(participants) < 2:
        return {"error": "party_too_small", "message": "Party must have at least 2 members for shared combat."}

    leader_chars = [p for p in participants if p.get("role") == "leader"]
    if not leader_chars:
        return {"error": "no_leader", "message": "Party has no leader."}
    leader_pid = int(leader_chars[0]["player_id"])
    if leader_pid != leader_discord_id:
        return {"error": "not_leader", "message": "Only the party leader can start the dungeon encounter."}

    # Order: leader first, then members by name
    leaders = [p for p in participants if p.get("role") == "leader"]
    members = [p for p in participants if p.get("role") != "leader"]
    members.sort(key=lambda x: (x.get("name") or ""))
    ordered = leaders + members
    discord_order: List[int] = [int(p["player_id"]) for p in ordered]

    dungeon_key = run["dungeon_key"]
    floor = int(run["current_floor"])
    cfg = DUNGEONS.get(dungeon_key)
    if not cfg:
        return {"error": "invalid_dungeon", "message": "Unknown dungeon."}

    try:
        enemy_key, is_boss = _enemy_key_for_dungeon_floor(cfg, floor)
    except (ValueError, TypeError):
        return {"error": "invalid_floor", "message": "Invalid dungeon floor."}

    leader_char = await char_svc.get_character(leader_discord_id)
    if not leader_char:
        return {"error": "no_character", "message": "Create a character first."}
    zone = ZONES.get(leader_char["current_zone"])
    if not zone:
        return {"error": "unknown_zone", "message": "Travel to a valid zone first."}

    if run_id in PARTY_DUNGEON_SESSIONS:
        pac = PARTY_DUNGEON_SESSIONS[run_id]
        if not pac.session.over:
            if pac.dungeon_key == dungeon_key and pac.dungeon_floor == floor:
                has_potion = await _has_healing_potion(db, leader_char["id"])
                can_potion = bool(has_potion) and not pac.potion_by_discord.get(leader_discord_id, False)
                return {
                    "error": "already_in_combat",
                    "state": serialize_activity_state(
                        pac, dict(leader_char), awaiting_action=True, can_potion=can_potion
                    ),
                }
        _clear_party_dungeon_session(pac)

    # Clear solo Activity sessions for all party members
    for did in discord_order:
        if did in ACTIVE_ACTIVITY:
            _clear_activity_session(did)
            ch = await char_svc.get_character(did)
            if ch:
                await db.execute("UPDATE characters SET combat_status='idle' WHERE id=$1", ch["id"])

    # Load combatants
    players_c: List[Combatant] = []
    party_char_to_discord: Dict[str, int] = {}
    for p in ordered:
        did = int(p["player_id"])
        ch = await char_svc.get_character(did)
        if not ch:
            return {"error": "no_character", "message": "A party member has no character."}
        if ch["level"] < cfg.level_req:
            return {
                "error": "level_too_low",
                "message": f"Everyone must be level {cfg.level_req}+ for this dungeon.",
            }
        st = await char_svc.total_stats(ch["id"])
        pl = _make_player(dict(ch), st)
        players_c.append(pl)
        party_char_to_discord[str(ch["id"])] = did

    enemy_c = _make_enemy(enemy_key, leader_char["level"], None, party_size=len(players_c))
    session = CombatSession(
        session_id=uuid4(),
        players=players_c,
        enemies=[enemy_c],
        is_boss=is_boss,
        enemy_key=enemy_key,
        zone_key=leader_char["current_zone"],
    )
    session.turn = 1
    engine = CombatEngine()
    log_lines: List[str] = []
    for pl in session.alive_players:
        log_lines.extend(engine.tick_turn(pl))
    if not session.alive_players:
        return {"error": "party_dead_start", "message": "Cannot start combat."}

    for did in discord_order:
        ch = await char_svc.get_character(did)
        if ch:
            await db.execute(
                "UPDATE characters SET combat_status='in_combat', last_combat=NOW(), pending_encounter=NULL WHERE id=$1",
                ch["id"],
            )

    hp0 = players_c[0].current_hp if players_c else 0
    ac = ActivityCombatState(
        session=session,
        log_lines=log_lines,
        potion_used=False,
        dungeon_key=dungeon_key,
        dungeon_floor=floor,
        started_at=datetime.now(timezone.utc),
        hp_start=hp0,
        party_run_id=run_id,
        party_discord_order=discord_order,
        party_char_to_discord=party_char_to_discord,
        party_turn_idx=0,
        potion_by_discord={},
    )
    PARTY_DUNGEON_SESSIONS[run_id] = ac
    for did in discord_order:
        DISCORD_TO_PARTY_RUN[did] = run_id

    has_potion = await _has_healing_potion(db, leader_char["id"])
    can_potion = bool(has_potion) and not ac.potion_by_discord.get(leader_discord_id, False)
    return {
        "ok": True,
        "guild_id": guild_id,
        "state": serialize_activity_state(
            ac, dict(leader_char), awaiting_action=True, can_potion=can_potion, viewer_discord_id=leader_discord_id
        ),
    }


def _queue_party_outcomes(
    ac: ActivityCombatState, payload: Dict[str, Any], exclude_discord: Optional[int] = None
) -> None:
    """Queue one-shot GET /combat/state delivery for party members who did not receive this payload via POST /action."""
    for did in ac.party_discord_order:
        if exclude_discord is not None and did == exclude_discord:
            continue
        PARTY_PENDING_OUTCOME[did] = payload


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
    run_id = DISCORD_TO_PARTY_RUN.get(discord_id)
    if run_id is not None:
        lock = _party_action_lock(run_id)
        async with lock:
            return await _process_party_activity_action_impl(bot, discord_id, guild_id, body, run_id)
    lock = _activity_action_lock(discord_id)
    async with lock:
        return await _process_activity_action_impl(bot, discord_id, guild_id, body)


async def _process_activity_action_impl(
    bot,
    discord_id: int,
    guild_id: Optional[int],
    body: Dict[str, Any],
) -> Dict[str, Any]:
    """Implementation for process_activity_action (must run under per-user lock)."""
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
            await _activity_fled(bot, guild_id, char, player, char_svc, db, ac)
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
            return await _finish_defeat(bot, guild_id, discord_id, char, player, char_svc, db, log_lines, ac)
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
            return await _finish_defeat(bot, guild_id, discord_id, char, player, char_svc, db, log_lines, ac)
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

    cost_mult = getattr(Settings, "RESOURCE_COST_MULT", {}).get(char["class"], 1.0)
    eff_cost = int(ab.cost * cost_mult) if ab.cost else 0

    async def _return_awaiting() -> Dict[str, Any]:
        has_potion = await _has_healing_potion(db, char_id)
        can_potion = bool(has_potion) and not ac.potion_used
        fresh = await char_svc.get_character(discord_id)
        return {
            "ok": True,
            "ended": False,
            "state": serialize_activity_state(ac, fresh, awaiting_action=True, can_potion=can_potion),
        }

    # Invalid ability: still your turn — do not run enemy phase (was causing "spam" feel).
    if ab.cost_type in ("mana", "energy", "rage") and player.current_res < eff_cost:
        log_lines.append(f"❌ Not enough {ab.cost_type} for **{ab.name}**!")
        return await _return_awaiting()
    if ability_key in player.ability_cooldowns:
        log_lines.append(f"⏳ **{ab.name}** is on cooldown!")
        return await _return_awaiting()

    ability_resolved = False
    if ab.cost_type in ("mana", "energy", "rage") and eff_cost:
        player.current_res = max(0, player.current_res - eff_cost)
    try:
        results = engine.use_ability(ability_key, player, [enemy], session=session)
        for r in results:
            log_lines.append(r.narrative)
        session.log.extend(results)
        ability_resolved = True
    except Exception as e:
        log.exception("activity combat ability error")
        log_lines.append(f"⚠️ **{ab.name}** failed: {str(e)[:80]}")
        try:
            results = engine.use_ability("auto_attack", player, [enemy], session=session)
            for r in results:
                log_lines.append(r.narrative)
            session.log.extend(results)
            ability_resolved = True
        except Exception as e2:
            log.exception("activity auto_attack fallback failed: %s", e2)

    if not ability_resolved:
        return await _return_awaiting()

    if session.over and session.players_won:
        return await _finish_victory(bot, guild_id, discord_id, char, session, player, char_svc, inv_svc, engine, db, log_lines, ac)

    if session.over:
        return await _finish_defeat(bot, guild_id, discord_id, char, player, char_svc, db, log_lines, ac)

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
            return await _finish_victory(bot, guild_id, discord_id, char, session, player, char_svc, inv_svc, engine, db, log_lines, ac)
        return await _finish_defeat(bot, guild_id, discord_id, char, player, char_svc, db, log_lines, ac)

    session.turn += 1
    fresh = await char_svc.get_character(discord_id)
    player2 = session.alive_players[0]
    ticks2 = engine.tick_turn(player2)
    log_lines.extend(ticks2)
    if player2.is_dead:
        return await _finish_defeat(bot, guild_id, discord_id, char, player2, char_svc, db, log_lines, ac)

    has_potion = await _has_healing_potion(db, char_id)
    can_potion = bool(has_potion) and not ac.potion_used
    return {
        "ok": True,
        "ended": False,
        "state": serialize_activity_state(ac, fresh, awaiting_action=True, can_potion=can_potion),
    }


async def _process_party_activity_action_impl(
    bot,
    discord_id: int,
    guild_id: Optional[int],
    body: Dict[str, Any],
    run_id: UUID,
) -> Dict[str, Any]:
    db = getattr(bot, "db", None)
    if db is None or db.pool is None:
        return {"error": "database_unavailable"}

    ac = PARTY_DUNGEON_SESSIONS.get(run_id)
    if not ac or not ac.party_run_id:
        return {"error": "no_session", "message": "Start a fight from the Dungeon tab first."}

    from services.character.character_service import CharacterService
    from services.character.inventory_service import InventoryService

    char_svc = CharacterService(db)
    inv_svc = InventoryService(db)
    char = await char_svc.get_character(discord_id)
    if not char:
        return {"error": "no_character"}

    session = ac.session
    engine = CombatEngine()
    log_lines = ac.log_lines
    char_id = char["id"]

    if session.over:
        _clear_party_dungeon_session(ac)
        return {"error": "session_over", "message": "Combat already ended."}

    alive_order = _alive_party_discord_order(ac)
    if not alive_order:
        return await _finish_party_defeat(bot, guild_id, ac, char_svc, db, log_lines, discord_id)

    if ac.party_turn_idx >= len(alive_order) or alive_order[ac.party_turn_idx] != discord_id:
        return {
            "error": "not_your_turn",
            "message": "Wait for your party member's turn.",
        }

    player = _find_player_for_discord(ac, session, discord_id)
    if not player:
        return {"error": "no_session", "message": "Combatant not found."}
    enemy = session.alive_enemies[0]

    flee = bool(body.get("flee"))
    potion = bool(body.get("potion"))
    ability_key = (body.get("ability") or body.get("ability_key") or "").strip()

    async def _await_state() -> Dict[str, Any]:
        has_potion = await _has_healing_potion(db, char_id)
        can_potion = bool(has_potion) and not ac.potion_by_discord.get(discord_id, False)
        fresh = await char_svc.get_character(discord_id)
        return {
            "ok": True,
            "ended": False,
            "state": serialize_activity_state(
                ac, fresh, awaiting_action=True, can_potion=can_potion, viewer_discord_id=discord_id
            ),
        }

    # ── Flee (whole party) ─────────────────────────────────────────────────
    if flee:
        flee_roll = Settings.FLEE_BASE_CHANCE + player.dodge_chance * 0.01
        if random.random() < flee_roll:
            log_lines.append("🏃 **The party flees from combat!**")
            for did in ac.party_discord_order:
                ch = await char_svc.get_character(did)
                if not ch:
                    continue
                pl = _find_player_for_discord(ac, session, did)
                if pl:
                    await _record_combat_session(
                        db,
                        ch["id"],
                        "fled",
                        ac.session.zone_key,
                        ac.started_at,
                        ac.session.turn,
                        ac.hp_start,
                        pl.current_hp,
                    )
                    await char_svc.sync_combat_hp(ch["id"], pl.current_hp, pl.current_res)
                await db.execute("UPDATE characters SET combat_status='idle' WHERE player_id=$1", did)
            out = {
                "ok": True,
                "ended": True,
                "outcome": {
                    "type": "flee",
                    "title": "🏃 Escaped!",
                    "lines": ["The party left the encounter."],
                },
            }
            _queue_party_outcomes(ac, out, exclude_discord=discord_id)
            _clear_party_dungeon_session(ac)
            return out
        log_lines.append("🚫 The party couldn't flee!")
        session.turn += 1
        ticks = engine.tick_turn(player)
        log_lines.extend(ticks)
        if player.is_dead:
            return await _finish_party_defeat(bot, guild_id, ac, char_svc, db, log_lines, discord_id)
        return await _await_state()

    # ── Potion ─────────────────────────────────────────────────────────────
    if potion:
        has_potion_row = await _has_healing_potion(db, char_id)
        if not has_potion_row:
            log_lines.append("❌ You don't have any healing potions!")
        elif ac.potion_by_discord.get(discord_id, False):
            log_lines.append("❌ You already used a potion this fight.")
        else:
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
            if ok:
                ac.potion_by_discord[discord_id] = True

        session.turn += 1
        ticks = engine.tick_turn(player)
        log_lines.extend(ticks)
        if player.is_dead:
            return await _finish_party_defeat(bot, guild_id, ac, char_svc, db, log_lines, discord_id)

        alive_order2 = _alive_party_discord_order(ac)
        ac.party_turn_idx += 1
        if ac.party_turn_idx >= len(alive_order2):
            ac.party_turn_idx = 0
            ended = await _party_enemy_round(
                bot, guild_id, ac, char_svc, inv_svc, engine, db, log_lines, discord_id
            )
            if ended is not None:
                return ended
        return await _await_state()

    # ── Ability ────────────────────────────────────────────────────────────
    if not ability_key:
        ability_key = "auto_attack"

    ab = ABILITIES.get(ability_key)
    if not ab:
        ability_key = "auto_attack"
        ab = ABILITIES.get("auto_attack", ABILITIES["auto_attack"])

    cost_mult = getattr(Settings, "RESOURCE_COST_MULT", {}).get(char["class"], 1.0)
    eff_cost = int(ab.cost * cost_mult) if ab.cost else 0

    if ab.cost_type in ("mana", "energy", "rage") and player.current_res < eff_cost:
        log_lines.append(f"❌ Not enough {ab.cost_type} for **{ab.name}**!")
        return await _await_state()
    if ability_key in player.ability_cooldowns:
        log_lines.append(f"⏳ **{ab.name}** is on cooldown!")
        return await _await_state()

    ability_resolved = False
    if ab.cost_type in ("mana", "energy", "rage") and eff_cost:
        player.current_res = max(0, player.current_res - eff_cost)
    try:
        results = engine.use_ability(ability_key, player, [enemy], session=session)
        for r in results:
            log_lines.append(r.narrative)
        session.log.extend(results)
        ability_resolved = True
    except Exception as e:
        log.exception("party activity combat ability error")
        log_lines.append(f"⚠️ **{ab.name}** failed: {str(e)[:80]}")
        try:
            results = engine.use_ability("auto_attack", player, [enemy], session=session)
            for r in results:
                log_lines.append(r.narrative)
            session.log.extend(results)
            ability_resolved = True
        except Exception as e2:
            log.exception("party auto_attack fallback failed: %s", e2)

    if not ability_resolved:
        return await _await_state()

    if session.over and session.players_won:
        return await _finish_party_victory(
            bot, guild_id, ac, char_svc, inv_svc, engine, db, log_lines, discord_id
        )

    if session.over:
        return await _finish_party_defeat(bot, guild_id, ac, char_svc, db, log_lines, discord_id)

    alive_order3 = _alive_party_discord_order(ac)
    ac.party_turn_idx += 1
    if ac.party_turn_idx >= len(alive_order3):
        ac.party_turn_idx = 0
        ended = await _party_enemy_round(
            bot, guild_id, ac, char_svc, inv_svc, engine, db, log_lines, discord_id
        )
        if ended is not None:
            return ended

    return await _await_state()


async def _party_enemy_round(
    bot,
    guild_id: Optional[int],
    ac: ActivityCombatState,
    char_svc,
    inv_svc,
    engine: CombatEngine,
    db,
    log_lines: List[str],
    acting_discord_id: int,
) -> Optional[Dict[str, Any]]:
    session = ac.session
    enemy = session.alive_enemies[0] if session.alive_enemies else session.enemies[0]

    e_ticks = engine.tick_turn(enemy)
    if e_ticks:
        log_lines.extend(e_ticks)

    if not enemy.is_dead:
        if session.is_boss:
            session.boss_phase = engine.boss_phase(enemy)
        # Party dungeon design: enemy damage applies to all alive party members.
        # Let engine choose the enemy ability, but always target the whole party.
        e_ab, _ = engine.enemy_turn(enemy, session.alive_players, session.is_boss, session.boss_phase)
        targets = list(session.alive_players)
        if targets:
            e_results = engine.use_ability(e_ab, enemy, targets, session=session)
            for r in e_results:
                log_lines.append(r.narrative)
            session.log.extend(e_results)

    if session.over:
        if session.players_won:
            return await _finish_party_victory(
                bot, guild_id, ac, char_svc, inv_svc, engine, db, log_lines, acting_discord_id
            )
        return await _finish_party_defeat(bot, guild_id, ac, char_svc, db, log_lines, acting_discord_id)

    session.turn += 1
    for pl in session.alive_players:
        log_lines.extend(engine.tick_turn(pl))

    alive_order = _alive_party_discord_order(ac)
    if not alive_order:
        return await _finish_party_defeat(bot, guild_id, ac, char_svc, db, log_lines, acting_discord_id)
    ac.party_turn_idx = 0
    return None


async def _finish_party_defeat(
    bot,
    guild_id: Optional[int],
    ac: ActivityCombatState,
    char_svc,
    db,
    log_lines: List[str],
    acting_discord_id: int,
) -> Dict[str, Any]:
    from services.dungeon.dungeon_service import DungeonService

    session = ac.session
    for did in ac.party_discord_order:
        ch = await char_svc.get_character(did)
        if not ch:
            continue
        pl = _find_player_for_discord(ac, session, did)
        hp_end = pl.current_hp if pl else 0
        await _record_combat_session(
            db,
            ch["id"],
            "defeat",
            ac.session.zone_key,
            ac.started_at,
            ac.session.turn,
            ac.hp_start,
            hp_end,
        )
        revive_hp = max(1, ch["max_hp"] // 5)
        await db.execute(
            "UPDATE characters SET current_hp=$2, combat_status='idle' WHERE id=$1",
            ch["id"],
            revive_hp,
        )

    run_id = ac.party_run_id
    if run_id:
        try:
            await DungeonService(db).complete_run(run_id, "defeat")
        except Exception as e:
            log.warning("party dungeon complete_run defeat: %s", e)

    lines = log_lines[-8:] + ["💀 The party was defeated — everyone revives with ~20% HP."]
    out = {
        "ok": True,
        "ended": True,
        "outcome": {"type": "defeat", "title": "💀 Defeated", "lines": lines},
    }
    _queue_party_outcomes(ac, out, exclude_discord=acting_discord_id)
    _clear_party_dungeon_session(ac)
    return out


async def _finish_party_victory(
    bot,
    guild_id: Optional[int],
    ac: ActivityCombatState,
    char_svc,
    inv_svc,
    engine: CombatEngine,
    db,
    log_lines: List[str],
    acting_discord_id: int,
) -> Dict[str, Any]:
    from services.achievement.achievement_service import AchievementService
    from services.dungeon.dungeon_service import DungeonService
    from services.quest.npc_quest_service import NPCQuestService
    from services.reward_multipliers import get_combined_reward_multipliers

    session = ac.session
    run_id = ac.party_run_id
    if not run_id:
        return {"error": "internal", "message": "Missing party run."}

    dungeon_svc = DungeonService(db)
    run = await dungeon_svc.get_run(run_id)
    if not run:
        _clear_party_dungeon_session(ac)
        return {"error": "internal", "message": "Dungeon run missing."}

    dungeon_key = run["dungeon_key"]
    cfg = DUNGEONS.get(dungeon_key)
    if not cfg:
        _clear_party_dungeon_session(ac)
        return {"error": "internal", "message": "Dungeon config missing."}

    floor = int(run["current_floor"])
    xp_mult, gold_mult, _boss_add = await get_combined_reward_multipliers(db, guild_id)
    n = max(1, len(ac.party_discord_order))
    base_xp = int(cfg.xp_reward * Settings.DUNGEON_XP_MULTIPLIER * xp_mult / n)
    base_gold = int(random.randint(cfg.gold_reward[0], cfg.gold_reward[1]) * Settings.DUNGEON_GOLD_MULTIPLIER * gold_mult / n)
    base_xp = max(1, base_xp)
    base_gold = max(0, base_gold)

    loot_lines_all: List[str] = []
    summary_lines: List[str] = []

    for did in ac.party_discord_order:
        ch = await char_svc.get_character(did)
        if not ch:
            continue
        pl = _find_player_for_discord(ac, session, did)
        await _record_combat_session(
            db,
            ch["id"],
            "victory",
            session.zone_key,
            ac.started_at,
            session.turn,
            ac.hp_start,
            pl.current_hp if pl else ch["current_hp"],
        )
        xp_result = await char_svc.award_xp(ch["id"], base_xp, xp_mult)
        await char_svc.add_gold(ch["id"], base_gold, "dungeon_party_floor")
        if pl:
            await char_svc.sync_combat_hp(ch["id"], pl.current_hp, pl.current_res)

        for _ in range(2 if session.is_boss else 1):
            loot = await inv_svc.generate_loot(dungeon_key, ch["level"], session.is_boss)
            if loot:
                ok, _ = await inv_svc.add_item(
                    ch["id"], loot["template"]["id"], loot["rarity"], bonus=loot["bonus"]
                )
                if ok:
                    rc = RARITIES[loot["rarity"]]
                    loot_lines_all.append(f"{ch['name']}: {rc.emoji} **{loot['template']['name']}**")

        if random.random() < 0.35:
            ok, _ = await inv_svc.add_item(ch["id"], "health_potion", "common", from_="combat_drop")
            if ok:
                loot_lines_all.append(f"{ch['name']}: 🧪 **Health Potion**")

        try:
            ach_svc = AchievementService(db)
            newly_earned = await ach_svc.check_and_award(ch["id"], "kill", {"is_boss": session.is_boss})
            for ach_id in newly_earned or []:
                ach = await ach_svc.get_achievement(ach_id)
                if ach:
                    loot_lines_all.append(f"{ch['name']}: 🏆 {ach.get('icon', '🏆')} {ach['name']}!")
        except Exception:
            pass

        try:
            quest_svc = NPCQuestService(db)
            qn = await quest_svc.check_kill_progress(
                ch["id"], session.enemy_key, session.zone_key, session.is_boss
            )
            loot_lines_all.extend([f"{ch['name']}: {x}" for x in (qn or [])])
        except Exception as e:
            log.error("Quest progress failed: %s", e)

        await db.execute("UPDATE characters SET combat_status='idle' WHERE id=$1", ch["id"])
        if xp_result.get("leveled_up"):
            summary_lines.append(f"{ch['name']} leveled up: {xp_result['old_level']} → {xp_result['new_level']}")

    if floor >= cfg.floors:
        await dungeon_svc.complete_run(run_id, "victory")
    else:
        await dungeon_svc.advance_floor(run_id)

    if guild_id:
        try:
            from services.milestones.milestone_service import MilestoneService

            ms = MilestoneService(db)
            completed = []
            completed.extend(
                await ms.increment(guild_id, "kills_total", 1, source="combat_kill", actor_id=acting_discord_id)
            )
            if session.is_boss:
                completed.extend(
                    await ms.increment(guild_id, "boss_kills", 1, source="combat_boss_kill", actor_id=acting_discord_id)
                )
            if base_gold > 0:
                completed.extend(
                    await ms.increment(
                        guild_id,
                        "gold_earned",
                        int(base_gold * n),
                        source="combat_gold",
                        actor_id=acting_discord_id,
                    )
                )
            if completed:
                await ms.announce_completions(bot, guild_id, completed)
        except Exception:
            pass

    out_lines = log_lines[-6:] + [
        f"🏆 **Floor {floor} cleared!** (~{base_xp * n:,} XP and ~{base_gold * n:,} 🪙 split across the party)",
        *summary_lines[:6],
    ]
    if loot_lines_all:
        out_lines.append("📦 " + " · ".join(loot_lines_all[:10]))

    out = {
        "ok": True,
        "ended": True,
        "outcome": {
            "type": "victory",
            "title": "🏆 Victory!",
            "lines": out_lines,
            "xp": base_xp * n,
            "gold": base_gold * n,
        },
    }
    _queue_party_outcomes(ac, out, exclude_discord=acting_discord_id)
    _clear_party_dungeon_session(ac)
    return out


async def _finish_defeat(
    bot,
    guild_id: Optional[int],
    discord_id: int,
    char: dict,
    player: Combatant,
    char_svc,
    db,
    log_lines: List[str],
    ac: ActivityCombatState,
) -> Dict[str, Any]:
    # Record combat session for Progress tab
    await _record_combat_session(
        db,
        char["id"],
        "defeat",
        ac.session.zone_key,
        ac.started_at,
        ac.session.turn,
        ac.hp_start,
        player.current_hp,
    )

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


async def _activity_fled(bot, guild_id, char, player, char_svc, db, ac: ActivityCombatState) -> None:
    # Record combat session for Progress tab
    await _record_combat_session(
        db,
        char["id"],
        "fled",
        ac.session.zone_key,
        ac.started_at,
        ac.session.turn,
        ac.hp_start,
        player.current_hp,
    )

    await char_svc.sync_combat_hp(char["id"], player.current_hp, player.current_res)
    await db.execute("UPDATE characters SET combat_status='idle' WHERE id=$1", char["id"])


async def _record_combat_session(
    db,
    char_id: str,
    outcome: str,
    zone: Optional[str],
    started_at: datetime,
    turn_count: int,
    hp_start: int,
    hp_end: int,
) -> None:
    """Record Activity combat to combat_sessions for Progress tab tracking."""
    try:
        session_id = await db.fetchval(
            """
            INSERT INTO combat_sessions
            (channel_id, session_type, zone, started_at, ended_at, is_active, outcome, turn_count)
            VALUES (0, 'solo', $1, $2, NOW(), FALSE, $3, $4)
            RETURNING id
            """,
            zone,
            started_at,
            outcome,
            turn_count,
        )
        await db.execute(
            """
            INSERT INTO combat_participants
            (session_id, character_id, is_player, hp_start, hp_end)
            VALUES ($1, $2, TRUE, $3, $4)
            """,
            session_id,
            char_id,
            hp_start,
            hp_end,
        )
    except Exception as e:
        log.warning("Failed to record combat session: %s", e)


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
    ac: ActivityCombatState,
) -> Dict[str, Any]:
    from services.achievement.achievement_service import AchievementService
    from services.quest.npc_quest_service import NPCQuestService

    from services.reward_multipliers import get_combined_reward_multipliers

    # Record combat session for Progress tab
    await _record_combat_session(
        db,
        char["id"],
        "victory",
        session.zone_key,
        ac.started_at,
        session.turn,
        ac.hp_start,
        player.current_hp,
    )

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


def ack_party_pending_outcome(discord_id: int) -> None:
    """Clear one-shot party outcome after the client applied it (avoid stealing GET between tabs)."""
    PARTY_PENDING_OUTCOME.pop(discord_id, None)


async def get_activity_combat_state(bot, discord_id: int) -> Dict[str, Any]:
    if discord_id in PARTY_PENDING_OUTCOME:
        out = PARTY_PENDING_OUTCOME.get(discord_id)
        return {"active": False, "ended_outcome": out}

    from services.character.character_service import CharacterService

    db = getattr(bot, "db", None)
    if db is None or db.pool is None:
        return {"active": False}

    char_svc = CharacterService(db)
    char = await char_svc.get_character(discord_id)
    if not char:
        _clear_activity_session(discord_id)
        return {"active": False}

    run_id = DISCORD_TO_PARTY_RUN.get(discord_id)
    if run_id is not None:
        ac = PARTY_DUNGEON_SESSIONS.get(run_id)
        if not ac:
            DISCORD_TO_PARTY_RUN.pop(discord_id, None)
            return {"active": False}
        has_potion = await _has_healing_potion(db, char["id"])
        can_potion = bool(has_potion) and not ac.potion_by_discord.get(discord_id, False)
        return {
            "active": True,
            "state": serialize_activity_state(
                ac, dict(char), awaiting_action=True, can_potion=can_potion, viewer_discord_id=discord_id
            ),
        }

    ac = ACTIVE_ACTIVITY.get(discord_id)
    if not ac:
        return {"active": False}

    has_potion = await _has_healing_potion(db, char["id"])
    can_potion = bool(has_potion) and not ac.potion_used
    return {
        "active": True,
        "state": serialize_activity_state(ac, char, awaiting_action=True, can_potion=can_potion),
    }
