"""
Embedded Activity PvP — turn-based duels using CombatEngine (player vs player as player/enemy slots).
"""

from __future__ import annotations

import logging
import random
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID, uuid4

from config.settings import ABILITY_UNLOCK_LEVELS, CLASSES, Settings, SPECIALIZATIONS
from services.combat.activity_combat import ACTIVE_ACTIVITY, _make_player
from services.combat.combat_engine import ABILITIES, CombatEngine, CombatSession, Combatant, StatusEffect

log = logging.getLogger("activity_pvp")

# match_id -> session
ACTIVE_PVP: Dict[str, "PvpRuntime"] = {}
# discord_id -> match_id
DISCORD_TO_MATCH: Dict[int, str] = {}
# queues: list of discord_ids waiting
QUEUE_CASUAL: List[int] = []
QUEUE_RANKED: List[int] = []
# challenge: target_discord_id -> {from_discord, from_name, mode, expires_ts}
CHALLENGE_INBOX: Dict[int, Dict[str, Any]] = {}
# sender waiting for accept: discord_id -> {target, started_ts}
CHALLENGE_OUTBOX: Dict[int, Dict[str, Any]] = {}

TURN_SECONDS = 90


@dataclass
class PvpRuntime:
    match_id: str
    mode: str  # casual | ranked
    guild_id: Optional[int]
    session: CombatSession
    discord_a: int
    discord_b: int
    char_a: dict
    char_b: dict
    turn: int  # 0 = A acts, 1 = B acts
    started_at: float
    log_ui: List[Dict[str, Any]] = field(default_factory=list)
    damage_dealt: Dict[int, int] = field(default_factory=dict)
    damage_taken: Dict[int, int] = field(default_factory=dict)
    crits: Dict[int, int] = field(default_factory=dict)
    log_seq: int = 0


def _log_line(rt: PvpRuntime, message: str, kind: str = "system") -> None:
    rt.log_seq += 1
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    rt.log_ui.append(
        {
            "id": f"{rt.match_id}-{rt.log_seq}",
            "timestamp": ts,
            "message": message,
            "type": kind,
        }
    )
    if len(rt.log_ui) > 40:
        rt.log_ui = rt.log_ui[-30:]


def _ability_options(char: dict, combatant: Combatant) -> List[Dict[str, Any]]:
    cls = CLASSES[char["class"]]
    keys = ["auto_attack"] + list(cls.starter_abilities)
    if char.get("specialization"):
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
        cd = combatant.ability_cooldowns.get(key, 0)
        out.append(
            {
                "key": key,
                "name": ab.name,
                "cooldown": cd,
                "max_cooldown": ab.cooldown,
                "description": (ab.description or "")[:160],
            }
        )
    return out[:12]


def _combatant_snapshot(c: Combatant, char: dict, discord_id: int) -> Dict[str, Any]:
    spec = char.get("specialization")
    spec_name = None
    if spec:
        sp = SPECIALIZATIONS.get(spec)
        if sp:
            spec_name = sp.name
    cls = CLASSES.get(char["class"])
    return {
        "user_id": str(discord_id),
        "username": "",
        "character_name": c.name,
        "level": char.get("level", 1),
        "class": cls.name if cls else char.get("class", ""),
        "spec": spec_name,
        "hp": c.current_hp,
        "max_hp": c.max_hp,
        "resource": c.current_res,
        "max_resource": c.max_res,
    }


def _serialize_match(rt: PvpRuntime, viewer_discord: int) -> Dict[str, Any]:
    sess = rt.session
    p1 = sess.players[0]
    p2 = sess.enemies[0]
    is_a = viewer_discord == rt.discord_a
    me_c, opp_c = (p1, p2) if is_a else (p2, p1)
    me_char, opp_char = (rt.char_a, rt.char_b) if is_a else (rt.char_b, rt.char_a)
    my_turn = (rt.turn == 0 and is_a) or (rt.turn == 1 and not is_a)

    my_did = rt.discord_a if is_a else rt.discord_b
    opp_did = rt.discord_b if is_a else rt.discord_a
    return {
        "match_id": rt.match_id,
        "status": "active",
        "mode": rt.mode,
        "is_your_turn": my_turn,
        "turn_timer": TURN_SECONDS,
        "player": _combatant_snapshot(me_c, me_char, my_did),
        "opponent": _combatant_snapshot(opp_c, opp_char, opp_did),
        "combat_log": rt.log_ui[-15:],
        "skills": _ability_options(me_char, me_c),
    }


def build_finished_match(
    rt: PvpRuntime,
    viewer_discord: int,
    winner_discord: int,
    loser_discord: int,
    rating_delta_viewer: Optional[int],
) -> Dict[str, Any]:
    sess = rt.session
    p1, p2 = sess.players[0], sess.enemies[0]
    duration = max(1, int(time.time() - rt.started_at))
    is_win = viewer_discord == winner_discord
    me_c, me_char = (p1, rt.char_a) if viewer_discord == rt.discord_a else (p2, rt.char_b)
    opp_c, opp_char = (p2, rt.char_b) if viewer_discord == rt.discord_a else (p1, rt.char_a)
    opp_did = rt.discord_b if viewer_discord == rt.discord_a else rt.discord_a
    return {
        "match_id": rt.match_id,
        "status": "finished",
        "mode": rt.mode,
        "result": "victory" if is_win else "defeat",
        "is_your_turn": False,
        "turn_timer": 0,
        "player": _combatant_snapshot(me_c, me_char, viewer_discord),
        "opponent": _combatant_snapshot(opp_c, opp_char, opp_did),
        "combat_log": rt.log_ui[-15:],
        "skills": [],
        "result_stats": {
            "damage_dealt": rt.damage_dealt.get(viewer_discord, 0),
            "damage_taken": rt.damage_taken.get(viewer_discord, 0),
            "crits": rt.crits.get(viewer_discord, 0),
            "duration_seconds": duration,
            "rating_delta": rating_delta_viewer if rt.mode == "ranked" else None,
        },
    }


def _rank_tier(rating: int) -> str:
    if rating < 1100:
        return "Bronze"
    if rating < 1300:
        return "Silver"
    if rating < 1500:
        return "Gold"
    if rating < 1700:
        return "Platinum"
    return "Diamond"


async def _get_or_create_pvp_stats(db, character_id: UUID) -> Dict[str, Any]:
    row = await db.fetchrow("SELECT * FROM pvp_stats WHERE character_id = $1", character_id)
    if row:
        return dict(row)
    await db.execute(
        """
        INSERT INTO pvp_stats (character_id, rating, wins, losses, draws, streak)
        VALUES ($1, 1500, 0, 0, 0, 0)
        ON CONFLICT (character_id) DO NOTHING
        """,
        character_id,
    )
    row = await db.fetchrow("SELECT * FROM pvp_stats WHERE character_id = $1", character_id)
    return dict(row) if row else {"rating": 1500, "wins": 0, "losses": 0, "draws": 0, "streak": 0}


def _win_rate(wins: int, losses: int, draws: int) -> float:
    total = wins + losses + draws
    if total <= 0:
        return 0.0
    return round(100.0 * wins / total, 1)


async def build_status_payload(bot, discord_id: int) -> Dict[str, Any]:
    from services.character.character_service import CharacterService

    db = getattr(bot, "db", None)
    if db is None or db.pool is None:
        return {"match_status": "idle", "error": "database_unavailable"}

    char_svc = CharacterService(db)
    char = await char_svc.get_character(discord_id)
    if not char:
        return {"match_status": "idle", "error": "no_character"}

    stats_row = await _get_or_create_pvp_stats(db, char["id"])
    rating = int(stats_row.get("rating") or 1500)
    wins = int(stats_row.get("wins") or 0)
    losses = int(stats_row.get("losses") or 0)
    draws = int(stats_row.get("draws") or 0)
    streak = int(stats_row.get("streak") or 0)

    out: Dict[str, Any] = {
        "match_status": "idle",
        "stats": {
            "rating": rating,
            "rank_tier": _rank_tier(rating),
            "wins": wins,
            "losses": losses,
            "draws": draws,
            "win_rate": _win_rate(wins, losses, draws),
            "streak": streak,
        },
        "player": {
            "user_id": str(discord_id),
            "username": "",
            "character_name": char["name"],
            "level": char["level"],
            "class": CLASSES[char["class"]].name if char.get("class") in CLASSES else char.get("class"),
            "spec": None,
            "hp": char.get("current_hp"),
            "max_hp": char.get("max_hp"),
            "resource": char.get("current_res"),
            "max_resource": char.get("max_res"),
        },
        "rules": {
            "bracket": f"Level {max(1, char['level'] - 10)}–{char['level'] + 10}",
            "level_range": f"{max(1, char['level'] - 10)}-{char['level'] + 10}",
            "gear_normalized": False,
        },
    }
    if char.get("specialization"):
        sp = SPECIALIZATIONS.get(char["specialization"])
        if sp:
            out["player"]["spec"] = sp.name

    mid = DISCORD_TO_MATCH.get(discord_id)
    if mid and mid in ACTIVE_PVP:
        out["match_status"] = "active"
        out["match"] = _serialize_match(ACTIVE_PVP[mid], discord_id)
        return out

    if discord_id in QUEUE_CASUAL:
        out["match_status"] = "queued"
        out["mode"] = "casual"
        return out
    if discord_id in QUEUE_RANKED:
        out["match_status"] = "queued"
        out["mode"] = "ranked"
        return out

    if discord_id in CHALLENGE_OUTBOX:
        ob = CHALLENGE_OUTBOX[discord_id]
        out["match_status"] = "challenged"
        out["challenge_target"] = str(ob.get("target"))
        elapsed = int(time.time() - float(ob.get("started", time.time())))
        out["challenge_timer"] = max(0, 120 - elapsed)
        return out

    if discord_id in CHALLENGE_INBOX:
        inc = CHALLENGE_INBOX[discord_id]
        out["incoming_challenge"] = {
            "from_discord_id": str(inc.get("from_discord")),
            "from_name": inc.get("from_name", "Player"),
            "mode": inc.get("mode", "casual"),
        }

    return out


def _remove_from_queues(did: int) -> None:
    if did in QUEUE_CASUAL:
        QUEUE_CASUAL.remove(did)
    if did in QUEUE_RANKED:
        QUEUE_RANKED.remove(did)


def _clear_pvp_for_discord(did: int) -> None:
    mid = DISCORD_TO_MATCH.pop(did, None)
    if mid and mid in ACTIVE_PVP:
        rt = ACTIVE_PVP.pop(mid, None)
        if rt:
            other = rt.discord_b if did == rt.discord_a else rt.discord_a
            DISCORD_TO_MATCH.pop(other, None)
    _remove_from_queues(did)
    CHALLENGE_OUTBOX.pop(did, None)
    CHALLENGE_INBOX.pop(did, None)


async def _try_match_queue(bot, mode: str) -> None:
    q = QUEUE_CASUAL if mode == "casual" else QUEUE_RANKED
    if len(q) < 2:
        return
    a, b = q[0], q[1]
    if a == b:
        return
    q.remove(a)
    q.remove(b)
    await _start_pvp_match(bot, a, b, mode, None)


async def _start_pvp_match(
    bot,
    discord_a: int,
    discord_b: int,
    mode: str,
    guild_id: Optional[int],
) -> None:
    from services.character.character_service import CharacterService

    db = getattr(bot, "db", None)
    if db is None:
        return
    char_svc = CharacterService(db)
    ca = await char_svc.get_character(discord_a)
    cb = await char_svc.get_character(discord_b)
    if not ca or not cb:
        return

    # Block if either in PvE iframe combat
    if discord_a in ACTIVE_ACTIVITY or discord_b in ACTIVE_ACTIVITY:
        return

    stats_a = await char_svc.total_stats(ca["id"])
    stats_b = await char_svc.total_stats(cb["id"])
    p1 = _make_player(dict(ca), stats_a)
    p2 = _make_player(dict(cb), stats_b)
    # Mark both as players for resource/rage rules on hit
    p1.is_player = True
    p2.is_player = True

    session = CombatSession(
        session_id=uuid4(),
        players=[p1],
        enemies=[p2],
        is_boss=False,
        enemy_key="pvp",
        zone_key="pvp",
    )
    engine = CombatEngine()
    # Opening ticks
    for line in engine.tick_turn(p1):
        pass
    for line in engine.tick_turn(p2):
        pass

    _remove_from_queues(discord_a)
    _remove_from_queues(discord_b)
    CHALLENGE_INBOX.pop(discord_a, None)
    CHALLENGE_INBOX.pop(discord_b, None)
    CHALLENGE_OUTBOX.pop(discord_a, None)
    CHALLENGE_OUTBOX.pop(discord_b, None)

    match_id = str(uuid4())
    rt = PvpRuntime(
        match_id=match_id,
        mode=mode,
        guild_id=guild_id,
        session=session,
        discord_a=discord_a,
        discord_b=discord_b,
        char_a=dict(ca),
        char_b=dict(cb),
        turn=0,
        started_at=time.time(),
    )
    _log_line(rt, f"⚔️ {p1.name} faces {p2.name} in a {mode} duel!", "system")
    ACTIVE_PVP[match_id] = rt
    DISCORD_TO_MATCH[discord_a] = match_id
    DISCORD_TO_MATCH[discord_b] = match_id


async def join_queue(bot, discord_id: int, mode: str, guild_id: Optional[int]) -> Dict[str, Any]:
    mid = DISCORD_TO_MATCH.get(discord_id)
    if mid and mid in ACTIVE_PVP:
        return {"ok": False, "error": "already_in_match"}
    if discord_id in ACTIVE_ACTIVITY:
        return {"ok": False, "error": "in_pve_combat"}
    _remove_from_queues(discord_id)
    if mode == "ranked":
        QUEUE_RANKED.append(discord_id)
    else:
        QUEUE_CASUAL.append(discord_id)
    await _try_match_queue(bot, mode)
    return {"ok": True}


async def leave_queue(discord_id: int) -> Dict[str, Any]:
    _remove_from_queues(discord_id)
    ob = CHALLENGE_OUTBOX.pop(discord_id, None)
    if ob and ob.get("target") is not None:
        try:
            CHALLENGE_INBOX.pop(int(ob["target"]), None)
        except (TypeError, ValueError):
            pass
    return {"ok": True}


async def send_challenge(bot, discord_id: int, target_user_id: str, guild_id: Optional[int]) -> Dict[str, Any]:
    try:
        tid = int(str(target_user_id).strip())
    except (TypeError, ValueError):
        return {"ok": False, "error": "invalid_target"}
    if tid == discord_id:
        return {"ok": False, "error": "cannot_challenge_self"}
    mid = DISCORD_TO_MATCH.get(discord_id)
    if mid and mid in ACTIVE_PVP:
        return {"ok": False, "error": "already_in_match"}

    from services.character.character_service import CharacterService

    db = getattr(bot, "db", None)
    char_svc = CharacterService(db)
    char = await char_svc.get_character(discord_id)
    if not char:
        return {"ok": False, "error": "no_character"}

    _remove_from_queues(discord_id)
    CHALLENGE_INBOX[tid] = {
        "from_discord": discord_id,
        "from_name": char["name"],
        "mode": "casual",
        "guild_id": guild_id,
    }
    CHALLENGE_OUTBOX[discord_id] = {"target": tid, "started": time.time()}
    return {"ok": True}


async def accept_challenge(bot, discord_id: int, guild_id: Optional[int]) -> Dict[str, Any]:
    if discord_id not in CHALLENGE_INBOX:
        return {"ok": False, "error": "no_challenge"}
    inc = CHALLENGE_INBOX.pop(discord_id)
    sender = int(inc["from_discord"])
    CHALLENGE_OUTBOX.pop(sender, None)
    mode = str(inc.get("mode", "casual"))
    await _start_pvp_match(bot, sender, discord_id, mode, guild_id)
    return {"ok": True}


def _current_combatants(rt: PvpRuntime) -> Tuple[Combatant, Combatant, dict, dict]:
    sess = rt.session
    return sess.players[0], sess.enemies[0], rt.char_a, rt.char_b


def _get_actor_for_turn(rt: PvpRuntime) -> Tuple[Combatant, Combatant, dict, int]:
    """Returns (attacker, defender, attacker_char_dict, attacker_discord)."""
    p1, p2, ca, cb = _current_combatants(rt)
    if rt.turn == 0:
        return p1, p2, ca, rt.discord_a
    return p2, p1, cb, rt.discord_b


async def process_pvp_action(
    bot,
    discord_id: int,
    guild_id: Optional[int],
    body: Dict[str, Any],
) -> Dict[str, Any]:
    from services.character.character_service import CharacterService

    db = getattr(bot, "db", None)
    if db is None:
        return {"error": "database_unavailable"}

    mid = DISCORD_TO_MATCH.get(discord_id)
    if not mid or mid not in ACTIVE_PVP:
        return {"error": "no_match"}

    rt = ACTIVE_PVP[mid]
    me, opp, me_char, me_discord = _get_actor_for_turn(rt)
    if me_discord != discord_id:
        return {"error": "not_your_turn"}

    action = (body.get("action") or "").strip().lower()
    skill_key = (body.get("skill_key") or body.get("skillKey") or "").strip()

    engine = CombatEngine()
    sess = rt.session

    # Start-of-turn tick
    ticks = engine.tick_turn(me)
    for t in ticks:
        _log_line(rt, t.replace("**", ""), "system")

    if action == "pass":
        _log_line(rt, f"{me.name} passes.", "system")
        rt.turn = 1 - rt.turn
        return {"ok": True, "match": _serialize_match(rt, discord_id)}

    if action == "defend":
        if me_char.get("class") == "warrior" and "defensive_stance" in ABILITIES:
            results = engine.use_ability("defensive_stance", me, [me], session=sess)
            for r in results:
                _log_line(rt, r.narrative.replace("**", ""), "system")
        else:
            _log_line(rt, f"{me.name} braces for impact (+dodge).", "system")
            me.add_status(StatusEffect.DODGE_UP, 12, 2, "defend")
        rt.turn = 1 - rt.turn
        return {"ok": True, "match": _serialize_match(rt, discord_id)}

    if action == "attack":
        skill_key = "auto_attack"
    elif action == "skill" and not skill_key:
        skill_key = "auto_attack"

    if action not in ("attack", "skill"):
        return {"error": "invalid_action"}

    ab = ABILITIES.get(skill_key) or ABILITIES["auto_attack"]
    cost_mult = getattr(Settings, "RESOURCE_COST_MULT", {}).get(me_char["class"], 1.0)
    eff_cost = int(ab.cost * cost_mult) if ab.cost else 0
    if ab.cost_type in ("mana", "energy", "rage") and me.current_res < eff_cost:
        _log_line(rt, f"Not enough resource for {ab.name}.", "system")
        return {"error": "not_enough_resource", "match": _serialize_match(rt, discord_id)}
    if skill_key in me.ability_cooldowns:
        _log_line(rt, f"{ab.name} is on cooldown.", "system")
        return {"error": "on_cooldown", "match": _serialize_match(rt, discord_id)}

    if ab.cost_type in ("mana", "energy", "rage") and eff_cost:
        me.current_res = max(0, me.current_res - eff_cost)

    other_did = rt.discord_b if discord_id == rt.discord_a else rt.discord_a
    results = engine.use_ability(skill_key, me, [opp], session=sess)
    for r in results:
        plain = (r.narrative or "").replace("**", "")
        if r.damage and r.damage > 0:
            rt.damage_dealt[discord_id] = rt.damage_dealt.get(discord_id, 0) + r.damage
            rt.damage_taken[other_did] = rt.damage_taken.get(other_did, 0) + r.damage
        if r.is_crit:
            rt.crits[discord_id] = rt.crits.get(discord_id, 0) + 1
        _log_line(rt, plain or f"{me.name} uses {ab.name}.", "damage" if r.damage else "system")

    if sess.over:
        winner_discord = rt.discord_a if sess.players_won else rt.discord_b
        loser_discord = rt.discord_b if winner_discord == rt.discord_a else rt.discord_a
        return await _finalize_pvp_match(bot, rt, winner_discord, loser_discord, guild_id, discord_id)

    for t in engine.tick_turn(opp):
        _log_line(rt, t.replace("**", ""), "system")

    if sess.over:
        winner_discord = rt.discord_a if sess.players_won else rt.discord_b
        loser_discord = rt.discord_b if winner_discord == rt.discord_a else rt.discord_a
        return await _finalize_pvp_match(bot, rt, winner_discord, loser_discord, guild_id, discord_id)

    rt.turn = 1 - rt.turn
    return {"ok": True, "match": _serialize_match(rt, discord_id)}


async def _finalize_pvp_match(
    bot,
    rt: PvpRuntime,
    winner_discord: int,
    loser_discord: int,
    guild_id: Optional[int],
    viewer_discord: int,
) -> Dict[str, Any]:
    from services.character.character_service import CharacterService

    db = getattr(bot, "db", None)
    char_svc = CharacterService(db)
    match_id = rt.match_id
    mode = rt.mode

    wc = await char_svc.get_character(winner_discord)
    lc = await char_svc.get_character(loser_discord)
    if not wc or not lc:
        DISCORD_TO_MATCH.pop(rt.discord_a, None)
        DISCORD_TO_MATCH.pop(rt.discord_b, None)
        ACTIVE_PVP.pop(match_id, None)
        return {"error": "character_missing"}

    p1 = rt.session.players[0]
    p2 = rt.session.enemies[0]
    if wc["id"] == rt.char_a["id"]:
        await char_svc.sync_combat_hp(wc["id"], p1.current_hp, p1.current_res)
    else:
        await char_svc.sync_combat_hp(wc["id"], p2.current_hp, p2.current_res)
    if lc["id"] == rt.char_a["id"]:
        await char_svc.sync_combat_hp(lc["id"], p1.current_hp, p1.current_res)
    else:
        await char_svc.sync_combat_hp(lc["id"], p2.current_hp, p2.current_res)

    wstats = await _get_or_create_pvp_stats(db, wc["id"])
    lst = await _get_or_create_pvp_stats(db, lc["id"])
    wr = int(wstats["rating"])
    lr = int(lst["rating"])
    delta_w: Optional[int] = None
    delta_l: Optional[int] = None

    if mode == "ranked":
        ew = 1.0 / (1.0 + 10 ** ((lr - wr) / 400.0))
        el = 1.0 / (1.0 + 10 ** ((wr - lr) / 400.0))
        k = 32
        new_wr = int(round(wr + k * (1.0 - ew)))
        new_lr = int(round(lr + k * (0.0 - el)))
        delta_w = new_wr - wr
        delta_l = new_lr - lr
        await db.execute(
            """
            UPDATE pvp_stats
            SET rating=$2, wins=wins+1,
                streak=CASE WHEN streak >= 0 THEN streak + 1 ELSE 1 END,
                updated_at=NOW()
            WHERE character_id=$1
            """,
            wc["id"],
            new_wr,
        )
        await db.execute(
            """
            UPDATE pvp_stats
            SET rating=$2, losses=losses+1,
                streak=CASE WHEN streak <= 0 THEN streak - 1 ELSE -1 END,
                updated_at=NOW()
            WHERE character_id=$1
            """,
            lc["id"],
            new_lr,
        )
    else:
        await db.execute(
            """
            UPDATE pvp_stats
            SET wins=wins+1, streak=CASE WHEN streak >= 0 THEN streak + 1 ELSE 1 END, updated_at=NOW()
            WHERE character_id=$1
            """,
            wc["id"],
        )
        await db.execute(
            """
            UPDATE pvp_stats
            SET losses=losses+1, streak=CASE WHEN streak <= 0 THEN streak - 1 ELSE -1 END, updated_at=NOW()
            WHERE character_id=$1
            """,
            lc["id"],
        )

    duration = max(1, int(time.time() - rt.started_at))
    await db.execute(
        """
        INSERT INTO pvp_match_history
        (character_id, opponent_character_id, opponent_name, mode, result, rating_delta, damage_dealt, damage_taken, crits, duration_seconds)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
        """,
        wc["id"],
        lc["id"],
        lc["name"],
        mode,
        "victory",
        delta_w,
        rt.damage_dealt.get(winner_discord, 0),
        rt.damage_taken.get(winner_discord, 0),
        rt.crits.get(winner_discord, 0),
        duration,
    )
    await db.execute(
        """
        INSERT INTO pvp_match_history
        (character_id, opponent_character_id, opponent_name, mode, result, rating_delta, damage_dealt, damage_taken, crits, duration_seconds)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
        """,
        lc["id"],
        wc["id"],
        wc["name"],
        mode,
        "defeat",
        delta_l,
        rt.damage_dealt.get(loser_discord, 0),
        rt.damage_taken.get(loser_discord, 0),
        rt.crits.get(loser_discord, 0),
        duration,
    )

    DISCORD_TO_MATCH.pop(rt.discord_a, None)
    DISCORD_TO_MATCH.pop(rt.discord_b, None)
    ACTIVE_PVP.pop(match_id, None)

    rd_viewer: Optional[int] = None
    if mode == "ranked" and delta_w is not None and delta_l is not None:
        rd_viewer = delta_w if viewer_discord == winner_discord else delta_l

    return {
        "ok": True,
        "ended": True,
        "winner": winner_discord,
        "match": build_finished_match(rt, viewer_discord, winner_discord, loser_discord, rd_viewer),
    }


async def get_history(bot, discord_id: int, page: int) -> Dict[str, Any]:
    from services.character.character_service import CharacterService

    db = getattr(bot, "db", None)
    if db is None:
        return {"matches": [], "has_more": False, "page": page}
    char_svc = CharacterService(db)
    char = await char_svc.get_character(discord_id)
    if not char:
        return {"matches": [], "has_more": False, "page": page}

    limit = 10
    offset = (page - 1) * limit
    rows = await db.fetch(
        """
        SELECT id, opponent_name, mode, result, rating_delta, created_at
        FROM pvp_match_history
        WHERE character_id = $1
        ORDER BY created_at DESC
        LIMIT $2 OFFSET $3
        """,
        char["id"],
        limit + 1,
        offset,
    )
    has_more = len(rows) > limit
    rows = rows[:limit]
    matches = []
    for r in rows:
        matches.append(
            {
                "match_id": str(r["id"]),
                "date": r["created_at"].strftime("%Y-%m-%d") if r["created_at"] else "",
                "opponent_name": r["opponent_name"],
                "result": r["result"],
                "mode": r["mode"],
                "rating_delta": r["rating_delta"],
            }
        )
    return {"matches": matches, "has_more": has_more, "page": page}
