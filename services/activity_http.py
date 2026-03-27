"""
╔══════════════════════════════════════════════════════════════════════════════╗
║   services/activity_http.py — HTTP API for Discord Embedded App (Activity)  ║
╚══════════════════════════════════════════════════════════════════════════════╝

Endpoints:
  POST /api/token              — Exchange OAuth code (from Embedded App SDK) for access_token
  GET  /api/game/inventory     — Bearer token → character + inventory rows
  GET  /api/game/equipment     — Bearer token → equipped items by slot
  GET  /api/game/combat/enemies — Bearer token → enemies/bosses in current zone
  GET  /api/game/combat/state   — Bearer token → active iframe combat (if any)
  POST /api/game/combat/start  — JSON { enemy_key, guild_id?, force? }
  POST /api/game/combat/action — JSON { ability, flee?, potion?, guild_id? }

Requires DISCORD_CLIENT_SECRET and DISCORD_APPLICATION_ID (same app as the bot).
See ACTIVITY_SETUP.md.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, Optional
from urllib.parse import unquote, urlencode
from uuid import UUID

import aiohttp
from aiohttp import web

from services.character.character_service import CharacterService
from services.character.inventory_service import InventoryService
from services.combat import activity_combat as activity_combat_api
from services.achievement.achievement_service import AchievementService
from services.blacksmith.blacksmith_service import BlacksmithService
from services.quest.npc_quest_service import NPCQuestService, NPC_TEMPLATES, FACTIONS, get_dynamic_intro, get_rep_level
from config.settings import ZONES, Settings, ENEMIES

log = logging.getLogger("activity_http")

DISCORD_API = "https://discord.com/api/v10"
OAUTH_TOKEN_URL = "https://discord.com/api/oauth2/token"


def _json_safe(obj: Any) -> Any:
    """Recursively convert DB values for JSON."""
    if obj is None:
        return None
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_json_safe(x) for x in obj]
    if isinstance(obj, UUID):
        return str(obj)
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, (bytes, memoryview)):
        return None
    return obj


def _cors_headers(request: web.Request) -> Dict[str, str]:
    origin = request.headers.get("Origin", "*")
    allowed = (os.getenv("ACTIVITY_CORS_ORIGINS") or "").strip()
    if allowed:
        parts = [x.strip() for x in allowed.split(",") if x.strip()]
        if origin in parts:
            allow_origin = origin
        else:
            allow_origin = parts[0] if parts else "*"
    else:
        allow_origin = origin if origin else "*"
    return {
        "Access-Control-Allow-Origin": allow_origin,
        "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
        "Access-Control-Allow-Headers": "Authorization, Content-Type",
        "Access-Control-Max-Age": "86400",
    }


@web.middleware
async def cors_middleware(request: web.Request, handler):
    if request.method == "OPTIONS":
        return web.Response(status=204, headers=_cors_headers(request))
    try:
        response = await handler(request)
    except web.HTTPException as ex:
        ex.headers.update(_cors_headers(request))
        raise
    for k, v in _cors_headers(request).items():
        response.headers.setdefault(k, v)
    return response


async def _discord_user_from_token(token: str) -> Optional[Dict[str, Any]]:
    timeout = aiohttp.ClientTimeout(total=15)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(
            f"{DISCORD_API}/users/@me",
            headers={"Authorization": f"Bearer {token}"},
        ) as resp:
            if resp.status != 200:
                log.debug("Discord @me returned %s", resp.status)
                return None
            return await resp.json()


def _oauth_redirect_attempts() -> list[Optional[str]]:
    """
    Discord requires token exchange redirect_uri to match OAuth2 → Redirects exactly.
    Try: (1) URL with trailing slash, (2) without, (3) omit redirect_uri (embedded-app pattern).
    """
    raw = (os.getenv("DISCORD_OAUTH_REDIRECT_URI") or os.getenv("ACTIVITY_PUBLIC_URL") or "").strip()
    out: list[Optional[str]] = []
    if raw:
        base = raw.rstrip().rstrip("/")
        for c in (base + "/", base):
            if c not in out:
                out.append(c)
    if None not in out:
        out.append(None)
    return out if out else [None]


async def _exchange_oauth_code(code: str, client_id: str, client_secret: str) -> Dict[str, Any]:
    """
    Exchange authorization code for tokens. Discord may require redirect_uri to match
    Developer Portal → OAuth2 → Redirects (same string as Activity public URL).
    """
    timeout = aiohttp.ClientTimeout(total=20)
    last_body = ""
    last_status = 0

    for redirect_uri in _oauth_redirect_attempts():
        form: Dict[str, str] = {
            "client_id": client_id,
            "client_secret": client_secret,
            "grant_type": "authorization_code",
            "code": code,
        }
        if redirect_uri:
            form["redirect_uri"] = redirect_uri

        body = urlencode(form)
        log.debug("OAuth token exchange try redirect_uri=%r", redirect_uri)

        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(
                OAUTH_TOKEN_URL,
                data=body,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            ) as resp:
                text = await resp.text()
                last_status = resp.status
                last_body = text
                if resp.status == 200:
                    return json.loads(text)

                # Retry next variant if Discord complains about redirect
                err_lower = text.lower()
                if "redirect" in err_lower or "invalid_grant" in err_lower:
                    log.warning(
                        "OAuth token exchange failed (%s) with redirect_uri=%r: %s",
                        resp.status,
                        redirect_uri,
                        text[:300],
                    )
                    continue
                break

    log.warning("OAuth token exchange failed: %s %s", last_status, last_body[:500])
    raise web.HTTPBadRequest(
        text=json.dumps(
            {
                "error": "token_exchange_failed",
                "detail": last_body[:400],
                "hint": (
                    "Add your Activity HTTPS URL under Developer Portal → OAuth2 → Redirects "
                    "(exact match), then set DISCORD_OAUTH_REDIRECT_URI or ACTIVITY_PUBLIC_URL "
                    "on the server to that same string."
                ),
            }
        ),
        content_type="application/json",
    )


def _client_id_for_app(bot) -> Optional[str]:
    cid = (os.getenv("DISCORD_APPLICATION_ID") or "").strip()
    if cid:
        return cid
    aid = getattr(bot, "application_id", None)
    if aid:
        return str(aid)
    return None


async def handle_token(request: web.Request) -> web.Response:
    bot = request.app["bot"]
    secret = (os.getenv("DISCORD_CLIENT_SECRET") or "").strip()
    client_id = _client_id_for_app(bot)
    if not secret or not client_id:
        raise web.HTTPServiceUnavailable(
            text=json.dumps({"error": "server_misconfigured", "hint": "Set DISCORD_CLIENT_SECRET and DISCORD_APPLICATION_ID"}),
            content_type="application/json",
        )
    try:
        body = await request.json()
    except json.JSONDecodeError:
        raise web.HTTPBadRequest(text=json.dumps({"error": "invalid_json"}), content_type="application/json")
    code = (body or {}).get("code")
    if not code or not isinstance(code, str):
        raise web.HTTPBadRequest(text=json.dumps({"error": "missing_code"}), content_type="application/json")

    token_payload = await _exchange_oauth_code(code, client_id, secret)
    access_token = token_payload.get("access_token")
    if not access_token:
        raise web.HTTPBadRequest(
            text=json.dumps({"error": "no_access_token"}),
            content_type="application/json",
        )
    return web.json_response({"access_token": access_token})


async def handle_inventory(request: web.Request) -> web.Response:
    bot = request.app["bot"]
    db = getattr(bot, "db", None)
    if db is None or db.pool is None:
        raise web.HTTPServiceUnavailable(text=json.dumps({"error": "database_unavailable"}), content_type="application/json")

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise web.HTTPUnauthorized(text=json.dumps({"error": "missing_bearer"}), content_type="application/json")
    token = auth_header[7:].strip()

    user = await _discord_user_from_token(token)
    if not user:
        raise web.HTTPUnauthorized(text=json.dumps({"error": "invalid_token"}), content_type="application/json")

    discord_id = int(user["id"])
    char_svc = CharacterService(db)
    inv_svc = InventoryService(db)

    char = await char_svc.get_character(discord_id)
    if not char:
        return web.json_response(
            _json_safe(
                {
                    "discord": {"id": str(discord_id), "username": user.get("username")},
                    "character": None,
                    "items": [],
                }
            )
        )

    items = await inv_svc.get_all(char["id"])
    char_dict = dict(char)
    return web.json_response(
        _json_safe(
            {
                "discord": {"id": str(discord_id), "username": user.get("username"), "global_name": user.get("global_name")},
                "character": char_dict,
                "items": items,
            }
        )
    )


def _guild_id_from_request(request: web.Request, body: Optional[Dict[str, Any]] = None) -> Optional[int]:
    raw = request.headers.get("X-Guild-Id") or request.headers.get("X-Guild-ID")
    if raw and str(raw).strip().isdigit():
        return int(str(raw).strip())
    if body and body.get("guild_id") is not None:
        g = body.get("guild_id")
        if isinstance(g, int):
            return g
        if isinstance(g, str) and g.strip().isdigit():
            return int(g.strip())
    return None


def _uuid_from_any(val: Any) -> UUID:
    """
    Robust UUID coercion.

    Note: asyncpg returns its own UUID type, which `uuid.UUID(...)` can't consume directly,
    but `str(asyncpg_uuid)` is a normal UUID string.
    """
    if isinstance(val, UUID):
        return val
    if val is None:
        raise ValueError("missing_uuid_value")
    return UUID(str(val))


async def handle_combat_enemies(request: web.Request) -> web.Response:
    bot = request.app["bot"]
    db = getattr(bot, "db", None)
    if db is None or db.pool is None:
        raise web.HTTPServiceUnavailable(text=json.dumps({"error": "database_unavailable"}), content_type="application/json")

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise web.HTTPUnauthorized(text=json.dumps({"error": "missing_bearer"}), content_type="application/json")
    token = auth_header[7:].strip()

    user = await _discord_user_from_token(token)
    if not user:
        raise web.HTTPUnauthorized(text=json.dumps({"error": "invalid_token"}), content_type="application/json")

    discord_id = int(user["id"])
    char_svc = CharacterService(db)
    char = await char_svc.get_character(discord_id)
    if not char:
        return web.json_response(_json_safe({"enemies": [], "error": "no_character"}))

    enemies = await activity_combat_api.list_zone_enemies(char)
    return web.json_response(_json_safe({"enemies": enemies}))


async def handle_combat_state(request: web.Request) -> web.Response:
    bot = request.app["bot"]
    db = getattr(bot, "db", None)
    if db is None or db.pool is None:
        raise web.HTTPServiceUnavailable(text=json.dumps({"error": "database_unavailable"}), content_type="application/json")

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise web.HTTPUnauthorized(text=json.dumps({"error": "missing_bearer"}), content_type="application/json")
    token = auth_header[7:].strip()

    user = await _discord_user_from_token(token)
    if not user:
        raise web.HTTPUnauthorized(text=json.dumps({"error": "invalid_token"}), content_type="application/json")

    discord_id = int(user["id"])
    payload = await activity_combat_api.get_activity_combat_state(bot, discord_id)
    return web.json_response(_json_safe(payload))


async def handle_combat_start(request: web.Request) -> web.Response:
    bot = request.app["bot"]
    db = getattr(bot, "db", None)
    if db is None or db.pool is None:
        raise web.HTTPServiceUnavailable(text=json.dumps({"error": "database_unavailable"}), content_type="application/json")

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise web.HTTPUnauthorized(text=json.dumps({"error": "missing_bearer"}), content_type="application/json")
    token = auth_header[7:].strip()

    user = await _discord_user_from_token(token)
    if not user:
        raise web.HTTPUnauthorized(text=json.dumps({"error": "invalid_token"}), content_type="application/json")

    discord_id = int(user["id"])
    try:
        body = await request.json()
    except json.JSONDecodeError:
        body = {}
    if not isinstance(body, dict):
        body = {}

    enemy_key = (body.get("enemy_key") or body.get("enemy") or "").strip()
    if not enemy_key:
        raise web.HTTPBadRequest(text=json.dumps({"error": "missing_enemy_key"}), content_type="application/json")

    force = bool(body.get("force"))
    guild_id = _guild_id_from_request(request, body)

    result = await activity_combat_api.start_activity_combat(bot, discord_id, enemy_key, guild_id, force=force)
    status = 200
    if result.get("error") == "already_in_combat":
        status = 409
    elif result.get("error"):
        status = 400
    return web.json_response(_json_safe(result), status=status)


async def handle_combat_action(request: web.Request) -> web.Response:
    bot = request.app["bot"]
    db = getattr(bot, "db", None)
    if db is None or db.pool is None:
        raise web.HTTPServiceUnavailable(text=json.dumps({"error": "database_unavailable"}), content_type="application/json")

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise web.HTTPUnauthorized(text=json.dumps({"error": "missing_bearer"}), content_type="application/json")
    token = auth_header[7:].strip()

    user = await _discord_user_from_token(token)
    if not user:
        raise web.HTTPUnauthorized(text=json.dumps({"error": "invalid_token"}), content_type="application/json")

    discord_id = int(user["id"])
    try:
        body = await request.json()
    except json.JSONDecodeError:
        body = {}
    if not isinstance(body, dict):
        body = {}

    guild_id = _guild_id_from_request(request, body)
    result = await activity_combat_api.process_activity_action(bot, discord_id, guild_id, body)
    status = 200
    if result.get("error"):
        status = 400
    return web.json_response(_json_safe(result), status=status)


async def handle_equipment(request: web.Request) -> web.Response:
    bot = request.app["bot"]
    db = getattr(bot, "db", None)
    if db is None or db.pool is None:
        raise web.HTTPServiceUnavailable(text=json.dumps({"error": "database_unavailable"}), content_type="application/json")

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise web.HTTPUnauthorized(text=json.dumps({"error": "missing_bearer"}), content_type="application/json")
    token = auth_header[7:].strip()

    user = await _discord_user_from_token(token)
    if not user:
        raise web.HTTPUnauthorized(text=json.dumps({"error": "invalid_token"}), content_type="application/json")

    discord_id = int(user["id"])
    char_svc = CharacterService(db)
    inv_svc = InventoryService(db)

    char = await char_svc.get_character(discord_id)
    if not char:
        return web.json_response(_json_safe({"character": None, "equipped": {}}))

    equipped = await inv_svc.get_equipped(char["id"])
    return web.json_response(_json_safe({"character": dict(char), "equipped": equipped}))


async def handle_progress(request: web.Request) -> web.Response:
    bot = request.app["bot"]
    db = getattr(bot, "db", None)
    if db is None or db.pool is None:
        raise web.HTTPServiceUnavailable(text=json.dumps({"error": "database_unavailable"}), content_type="application/json")

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise web.HTTPUnauthorized(text=json.dumps({"error": "missing_bearer"}), content_type="application/json")
    token = auth_header[7:].strip()

    user = await _discord_user_from_token(token)
    if not user:
        raise web.HTTPUnauthorized(text=json.dumps({"error": "invalid_token"}), content_type="application/json")

    discord_id = int(user["id"])
    char_svc = CharacterService(db)
    char = await char_svc.get_character(discord_id)
    if not char:
        return web.json_response(
            _json_safe(
                {
                    "character": None,
                    "stats": {
                        "total_combats": 0,
                        "wins": 0,
                        "losses": 0,
                        "fled": 0,
                        "win_rate": 0.0,
                    },
                    "achievements": [],
                    "history": [],
                }
            )
        )

    ach_svc = AchievementService(db)
    earned = await ach_svc.get_character_achievements(char["id"])

    # combat_sessions may be sparse in some deployments, so we gracefully handle empty history.
    combat_rows = await db.fetch(
        """
        SELECT cs.outcome, cs.started_at, cs.ended_at, cs.zone
        FROM combat_sessions cs
        JOIN combat_participants cp ON cp.session_id = cs.id
        WHERE cp.character_id = $1
          AND cp.is_player = TRUE
        ORDER BY COALESCE(cs.ended_at, cs.started_at) DESC
        LIMIT 30
        """,
        char["id"],
    )

    wins = sum(1 for r in combat_rows if (r.get("outcome") or "") == "victory")
    losses = sum(1 for r in combat_rows if (r.get("outcome") or "") in ("defeat", "timeout"))
    fled = sum(1 for r in combat_rows if (r.get("outcome") or "") == "fled")
    total = len(combat_rows)
    win_rate = float(wins / total) if total else 0.0

    # Fallback activity feed from gold log where reason/source indicates combat-style rewards.
    gold_rows = await db.fetch(
        """
        SELECT amount, reason, source, created_at
        FROM gold_log
        WHERE character_id = $1
          AND amount > 0
          AND (
            source::text = 'combat_drop'
            OR reason ILIKE '%combat%'
            OR reason ILIKE '%drop%'
          )
        ORDER BY created_at DESC
        LIMIT 15
        """,
        char["id"],
    )

    history = [
        {
            "type": "combat_gold",
            "amount": int(r["amount"] or 0),
            "reason": r.get("reason") or "combat",
            "source": str(r.get("source") or ""),
            "at": r.get("created_at"),
        }
        for r in gold_rows
    ]

    # Merge combat rows into history for richer feed.
    for r in combat_rows[:15]:
        history.append(
            {
                "type": "combat_session",
                "outcome": r.get("outcome") or "unknown",
                "zone": r.get("zone"),
                "at": r.get("ended_at") or r.get("started_at"),
            }
        )

    history = sorted(history, key=lambda x: str(x.get("at") or ""), reverse=True)[:20]

    payload = {
        "character": {
            "name": char.get("name"),
            "level": char.get("level"),
            "gold": char.get("gold"),
            "last_combat": char.get("last_combat"),
        },
        "stats": {
            "total_combats": total,
            "wins": wins,
            "losses": losses,
            "fled": fled,
            "win_rate": win_rate,
        },
        "achievements": [
            {
                "id": a.get("id"),
                "name": a.get("name"),
                "description": a.get("description"),
                "icon": a.get("icon") or "🏆",
                "points": a.get("points") or 0,
                "category": a.get("category"),
                "earned_at": a.get("earned_at"),
            }
            for a in earned[:25]
        ],
        "history": history,
    }
    return web.json_response(_json_safe(payload))


async def _authed_discord_user_and_char(request: web.Request) -> tuple[dict, int, dict, Any]:
    bot = request.app["bot"]
    db = getattr(bot, "db", None)
    if db is None or db.pool is None:
        raise web.HTTPServiceUnavailable(text=json.dumps({"error": "database_unavailable"}), content_type="application/json")

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise web.HTTPUnauthorized(text=json.dumps({"error": "missing_bearer"}), content_type="application/json")
    token = auth_header[7:].strip()

    user = await _discord_user_from_token(token)
    if not user:
        raise web.HTTPUnauthorized(text=json.dumps({"error": "invalid_token"}), content_type="application/json")

    discord_id = int(user["id"])
    char_svc = CharacterService(db)
    char = await char_svc.get_character(discord_id)
    return user, discord_id, dict(char) if char else None, db


async def handle_map(request: web.Request) -> web.Response:
    """List zones for Explore tab."""
    _user, discord_id, char, db = await _authed_discord_user_and_char(request)
    if not char:
        return web.json_response(_json_safe({"zones": [], "error": "no_character"}))

    out = []
    for key, z in sorted(ZONES.items(), key=lambda kv: kv[1].level_range[0]):
        players = await db.fetchval(
            "SELECT COUNT(*) FROM characters WHERE current_zone=$1 AND is_active=TRUE",
            key,
        ) or 0
        zs = await db.fetchrow("SELECT boss_alive FROM zone_state WHERE zone_key=$1", key)
        boss_alive = True if (not zs or zs.get("boss_alive") is None) else bool(zs["boss_alive"])
        out.append(
            {
                "key": key,
                "name": z.name,
                "emoji": z.emoji,
                "description": z.description,
                "level_min": z.level_range[0],
                "level_max": z.level_range[1],
                "faction": z.faction,
                "players": int(players),
                "boss_alive": boss_alive,
                "is_current": key == char.get("current_zone"),
            }
        )
    return web.json_response(_json_safe({"zones": out, "current_zone": char.get("current_zone")}))


def _npc_for_quest_id(quest_id: str) -> Optional[Dict[str, Any]]:
    for npc_id, npc in NPC_TEMPLATES.items():
        for q in npc.get("quests", []):
            if q.get("id") == quest_id:
                return {"npc_id": npc_id, "npc_name": npc.get("name"), "npc_title": npc.get("title")}
    return None


def _parse_meta_json(meta: Any) -> Dict[str, Any]:
    if meta is None:
        return {}
    if isinstance(meta, dict):
        return meta
    if isinstance(meta, str):
        try:
            return json.loads(meta)
        except Exception:
            return {}
    return {}


async def handle_quests(request: web.Request) -> web.Response:
    """Quest log for Activity hybrid UX."""
    _user, discord_id, char, db = await _authed_discord_user_and_char(request)
    if not char:
        return web.json_response(_json_safe({"ok": False, "error": "no_character", "quests": []}), status=400)

    qs = NPCQuestService(db)
    char_id = _uuid_from_any(char["id"])
    active = await qs.get_active_quests(char_id)

    out = []
    for q in active:
        quest_id = q.get("quest_id")
        steps = q.get("steps") or []
        cur_step = int(q.get("current_step") or 1)
        idx = max(0, cur_step - 1)
        step = steps[idx] if idx < len(steps) else None
        objective = (step or {}).get("objective")
        check = (step or {}).get("completion_check") or {}
        meta = _parse_meta_json(q.get("metadata"))

        progress = None
        if check.get("type") == "kill_enemy":
            needed = int(check.get("count") or 1)
            k = f"kills_{check.get('value')}"
            progress = {"current": int(meta.get(k, 0) or 0), "needed": needed}
        elif check.get("type") == "kill_any_zone":
            needed = int(check.get("count") or 1)
            k = f"kills_zone_{check.get('value')}"
            progress = {"current": int(meta.get(k, 0) or 0), "needed": needed}
        elif check.get("type") == "kill_boss_zone":
            needed = int(check.get("count") or 1)
            k = f"boss_kills_{check.get('value')}"
            progress = {"current": int(meta.get(k, 0) or 0), "needed": needed}

        npc_info = _npc_for_quest_id(quest_id) if quest_id else None
        chk = {
            "type": check.get("type"),
            "value": check.get("value"),
            "count": check.get("count"),
        }
        out.append(
            {
                "quest_id": quest_id,
                "state": q.get("state"),
                "quest_name": q.get("quest_name"),
                "quest_desc": q.get("quest_desc"),
                "current_step": cur_step,
                "total_steps": q.get("total_steps"),
                "objective": objective,
                "completion_check": chk,
                "progress": progress,
                "expires_at": q.get("expires_at"),
                **(npc_info or {}),
            }
        )

    return web.json_response(_json_safe({"ok": True, "quests": out}))


async def handle_travel(request: web.Request) -> web.Response:
    """Travel to a zone key (Explore tab)."""
    _user, discord_id, char, db = await _authed_discord_user_and_char(request)
    if not char:
        return web.json_response(_json_safe({"ok": False, "error": "no_character"}), status=400)

    try:
        body = await request.json()
    except json.JSONDecodeError:
        body = {}
    if not isinstance(body, dict):
        body = {}

    zone_key = (body.get("zone_key") or body.get("zone") or "").strip()
    if not zone_key or zone_key not in ZONES:
        return web.json_response(_json_safe({"ok": False, "error": "invalid_zone"}), status=400)

    if char.get("current_zone") == zone_key:
        return web.json_response(_json_safe({"ok": True, "message": "Already here.", "zone_key": zone_key}))

    z = ZONES[zone_key]
    if int(char.get("level") or 1) < z.level_range[0]:
        return web.json_response(
            _json_safe(
                {
                    "ok": False,
                    "error": "level_too_low",
                    "message": f"Need level {z.level_range[0]} for {z.name}.",
                }
            ),
            status=400,
        )

    # zone_state counters (best-effort)
    try:
        await db.execute(
            "UPDATE zone_state SET active_players=GREATEST(0,active_players-1) WHERE zone_key=$1",
            char.get("current_zone"),
        )
    except Exception:
        pass
    await db.execute("UPDATE characters SET current_zone=$2 WHERE id=$1", _uuid_from_any(char["id"]), zone_key)
    try:
        await db.execute(
            "UPDATE zone_state SET active_players=active_players+1 WHERE zone_key=$1",
            zone_key,
        )
    except Exception:
        pass

    # refresh char
    char_svc = CharacterService(db)
    fresh = await char_svc.get_character(discord_id)
    return web.json_response(_json_safe({"ok": True, "character": dict(fresh), "zone_key": zone_key}))


async def handle_explore(request: web.Request) -> web.Response:
    """Roll an explore outcome (loot/safe/enemy/boss) and possibly discover an NPC."""
    bot = request.app["bot"]
    user, discord_id, char, db = await _authed_discord_user_and_char(request)
    if not char:
        return web.json_response(_json_safe({"ok": False, "error": "no_character"}), status=400)

    try:
        body = await request.json()
    except (json.JSONDecodeError, ValueError, TypeError):
        body = {}
    if not isinstance(body, dict):
        body = {}
    guild_id = _guild_id_from_request(request, body)

    char_svc = CharacterService(db)
    inv_svc = InventoryService(db)
    quest_svc = NPCQuestService(db)

    # combat gate similar to /explore
    if (char.get("combat_status") or "") == "in_combat":
        return web.json_response(_json_safe({"ok": False, "error": "in_combat", "message": "Finish your fight first."}), status=409)

    cd = await char_svc.on_cooldown(_uuid_from_any(char["id"]), "explore")
    if cd:
        return web.json_response(_json_safe({"ok": False, "error": "cooldown", "cooldown_s": int(cd)}), status=429)

    zone = ZONES.get(char.get("current_zone"))
    if not zone:
        return web.json_response(_json_safe({"ok": False, "error": "unknown_zone"}), status=400)
    if int(char.get("level") or 1) < zone.level_range[0]:
        return web.json_response(_json_safe({"ok": False, "error": "level_too_low", "message": f"Need level {zone.level_range[0]}."}), status=400)

    # bump zone_state counters best-effort
    try:
        await db.execute(
            "UPDATE zone_state SET active_players=active_players+1, kills_today=kills_today+1 WHERE zone_key=$1",
            char.get("current_zone"),
        )
    except Exception:
        pass

    from services.exploration.zone_explore import roll_explore_outcome
    from services.reward_multipliers import get_combined_reward_multipliers

    xp_mult, gold_mult, boss_add = await get_combined_reward_multipliers(db, guild_id)
    outcome = roll_explore_outcome(zone, boss_add)

    cooldown = Settings.EXPLORE_COOLDOWN if outcome["type"] in ("enemy", "boss") else 10
    await char_svc.set_cooldown(_uuid_from_any(char["id"]), "explore", cooldown)

    reward = {}
    pending = None
    if outcome["type"] == "boss":
        pending = outcome["key"]
        await db.execute("UPDATE characters SET pending_encounter=$2 WHERE id=$1", _uuid_from_any(char["id"]), pending)
    elif outcome["type"] == "loot":
        xp0 = random.randint(5, 15 + int(char.get("level") or 1))
        g0 = random.randint(1, 5 + int(char.get("level") or 1) // 2)
        xp_res = await char_svc.award_xp(_uuid_from_any(char["id"]), xp0, xp_mult)
        gold = int(g0 * gold_mult)
        await char_svc.add_gold(_uuid_from_any(char["id"]), gold, "exploration")
        reward = {"xp": int(xp_res.get("xp_gained") or 0), "gold": gold, "base_xp": xp0, "base_gold": g0}
    elif outcome["type"] == "safe":
        xp0 = random.randint(3, 8)
        xp_res = await char_svc.award_xp(_uuid_from_any(char["id"]), xp0, xp_mult)
        reward = {"xp": int(xp_res.get("xp_gained") or 0), "base_xp": xp0}

    npc_payload = None
    try:
        npc_encounter = await quest_svc.roll_npc_encounter(_uuid_from_any(char["id"]), char.get("current_zone"))
        if npc_encounter:
            npc_id = npc_encounter["npc_id"]
            npc_data = npc_encounter["npc_data"]
            already = npc_encounter["already_met"]
            if not already:
                await quest_svc.discover_npc(_uuid_from_any(char["id"]), npc_id, char.get("current_zone"))
            npc_payload = {
                "npc_id": npc_id,
                "name": npc_data.get("name"),
                "title": npc_data.get("title"),
                "discovery_hint": npc_data.get("discovery_hint"),
                "already_met": already,
            }
    except Exception as e:
        log.warning("NPC encounter roll failed: %s", e)

    # refresh char snapshot for UI
    fresh = await char_svc.get_character(discord_id)
    return web.json_response(
        _json_safe(
            {
                "ok": True,
                "zone": {"key": char.get("current_zone"), "name": zone.name, "emoji": zone.emoji, "level_min": zone.level_range[0], "level_max": zone.level_range[1]},
                "outcome": outcome,
                "reward": reward,
                "reward_multipliers": {
                    "xp": xp_mult,
                    "gold": gold_mult,
                    "explore_boss_chance_add": boss_add,
                },
                "cooldown_s": cooldown,
                "npc": npc_payload,
                "character": dict(fresh) if fresh else None,
            }
        )
    )


async def handle_live_events(request: web.Request) -> web.Response:
    """Active guild live events (for Activity banner / debugging)."""
    _user, discord_id, char, db = await _authed_discord_user_and_char(request)
    if not char:
        return web.json_response(_json_safe({"ok": False, "error": "no_character", "events": []}), status=400)

    guild_id = _guild_id_from_request(request, {})
    if not guild_id:
        return web.json_response(_json_safe({"ok": True, "events": []}))

    from services.live_events.live_event_service import LiveEventService

    svc = LiveEventService(db)
    rows = await svc.list_active_public(guild_id)
    return web.json_response(_json_safe({"ok": True, "events": rows}))


async def handle_npc_interact(request: web.Request) -> web.Response:
    """Trigger the NPC DM interaction/quest offer flow (Activity button)."""
    bot = request.app["bot"]
    user, discord_id, char, db = await _authed_discord_user_and_char(request)
    if not char:
        return web.json_response(_json_safe({"ok": False, "error": "no_character"}), status=400)

    try:
        body = await request.json()
    except json.JSONDecodeError:
        body = {}
    if not isinstance(body, dict):
        body = {}

    npc_search = (body.get("npc") or body.get("npc_name") or "").strip()
    quest_svc = NPCQuestService(db)
    char_id = _uuid_from_any(char["id"])

    npc_id = quest_svc.find_npc_by_name(npc_search) if npc_search else None
    if not npc_id:
        # If not specified, try the most recent discovery in this zone.
        row = await db.fetchrow(
            "SELECT npc_id FROM npc_discoveries WHERE character_id=$1 AND zone_found=$2 ORDER BY discovered_at DESC LIMIT 1",
            char_id,
            char.get("current_zone"),
        )
        npc_id = row["npc_id"] if row else None
    if not npc_id or npc_id not in NPC_TEMPLATES:
        return web.json_response(_json_safe({"ok": False, "error": "npc_not_found"}), status=404)

    # Check discovery
    state = await quest_svc.get_npc_state(char_id, npc_id)
    if not state:
        return web.json_response(_json_safe({"ok": False, "error": "npc_not_discovered"}), status=400)

    npc_data = NPC_TEMPLATES[npc_id]

    # First: if player is turning in / talking for an active quest step, process that.
    talk_result = await quest_svc.check_talk_to_npc(char_id, npc_id)
    if talk_result and talk_result.get("complete"):
        rewards = await quest_svc.complete_quest(char_id, talk_result["quest_id"])
        if not rewards:
            return web.json_response(
                _json_safe(
                    {
                        "ok": False,
                        "error": "quest_complete_failed",
                        "message": "Could not complete quest (it may have expired).",
                    }
                ),
                status=400,
            )

        char_svc = CharacterService(db)
        inv_svc = InventoryService(db)
        # Grant rewards (same semantics as /interact flow).
        if rewards.get("xp"):
            await char_svc.award_xp(char_id, int(rewards["xp"]))
        if rewards.get("gold"):
            await char_svc.add_gold(char_id, int(rewards["gold"]), "quest_reward", "quest_reward")
        if rewards.get("items"):
            for template_id in rewards["items"]:
                tmpl = await db.fetchrow("SELECT rarity FROM item_templates WHERE id = $1", template_id)
                rarity = tmpl["rarity"] if tmpl else "common"
                await inv_svc.add_item(char_id, template_id, rarity=rarity)
        if rewards.get("reputation"):
            for faction_id, amount in rewards["reputation"].items():
                await quest_svc.add_reputation(char_id, faction_id, int(amount))

        completed_quest_ids = [q["quest_id"] for q in await quest_svc.get_completed_quests(char_id)]
        next_quest = quest_svc.get_next_quest_for_npc(npc_id, completed_quest_ids)
        reward_summary = {
            "xp": int(rewards.get("xp") or 0),
            "gold": int(rewards.get("gold") or 0),
            "items": list(rewards.get("items") or []),
            "reputation": {k: int(v) for k, v in (rewards.get("reputation") or {}).items()},
        }
        return web.json_response(
            _json_safe(
                {
                    "ok": True,
                    "message": "Quest completed and rewards granted.",
                    "npc_id": npc_id,
                    "quest_completed": True,
                    "rewards": reward_summary,
                    "next_quest_available": bool(next_quest),
                }
            )
        )
    if talk_result and not talk_result.get("complete"):
        next_step = talk_result.get("next_step") or {}
        return web.json_response(
            _json_safe(
                {
                    "ok": True,
                    "message": f"Quest step updated: {next_step.get('objective', 'Next objective updated.')}",
                    "npc_id": npc_id,
                    "quest_step_updated": True,
                }
            )
        )

    # Determine next quest
    completed_quest_ids = [q["quest_id"] for q in await quest_svc.get_completed_quests(char_id)]
    next_quest = quest_svc.get_next_quest_for_npc(npc_id, completed_quest_ids)
    if not next_quest:
        return web.json_response(_json_safe({"ok": True, "message": "No quests available.", "npc_id": npc_id}))

    # Level requirement
    if int(char.get("level") or 1) < int(next_quest.get("level_req", 1) or 1):
        return web.json_response(_json_safe({"ok": False, "error": "level_too_low", "message": f"Need level {next_quest['level_req']}."}), status=400)

    # Prevent duplicate offers / accepts: reserve DB row before DM (Activity spam)
    qid = next_quest["id"]
    ins_row = await quest_svc.try_insert_quest_offered(char_id, npc_id, qid)
    if not ins_row:
        prog = await quest_svc.get_quest_progress(char_id, qid)
        if prog and prog.get("state") == "expired":
            await db.execute(
                "DELETE FROM quest_progress WHERE character_id = $1 AND quest_id = $2 AND state = 'expired'",
                char_id,
                qid,
            )
            ins_row = await quest_svc.try_insert_quest_offered(char_id, npc_id, qid)
    if not ins_row:
        prog = await quest_svc.get_quest_progress(char_id, qid)
        if prog and prog.get("state") == "active":
            return web.json_response(
                _json_safe(
                    {
                        "ok": False,
                        "error": "quest_already_active",
                        "message": "You already have this quest active. Finish it (or abandon) before taking a new offer.",
                    }
                ),
                status=400,
            )
        if prog and prog.get("state") == "offered":
            return web.json_response(
                _json_safe(
                    {
                        "ok": False,
                        "error": "quest_offer_pending",
                        "message": "You already have a pending quest offer — check your DMs.",
                    }
                ),
                status=400,
            )
        return web.json_response(
            _json_safe({"ok": False, "error": "quest_unavailable", "message": "Could not start quest offer."}),
            status=400,
        )

    # Send DM with buttons (release reserved row if DM cannot be sent)
    try:
        uobj = bot.get_user(discord_id) or await bot.fetch_user(discord_id)
        dm = await uobj.create_dm()
    except Exception:
        await quest_svc.cancel_quest_offer(char_id, qid)
        return web.json_response(_json_safe({"ok": False, "error": "dm_forbidden", "message": "Enable DMs from server members."}), status=403)

    # Reuse the same UI view class from QuestCog
    from cogs.quest.quest_cog import QuestOfferView

    char_class = char.get("class", "warrior")
    char_level = int(char.get("level") or 1)
    intro_text = get_dynamic_intro(npc_id, npc_data, char_class, char_level)

    import discord as _discord

    embed = _discord.Embed(
        title=f"{npc_data.get('title','')} {npc_data.get('name','')}".strip(),
        description=intro_text,
        color=0x4A90E2,
    )
    embed.add_field(
        name="📜 Quest Available",
        value=f"**{next_quest['name']}**\n{next_quest['description']}",
        inline=False,
    )
    rewards = next_quest.get("rewards", {}) or {}
    reward_lines = []
    if rewards.get("xp"):
        reward_lines.append(f"⭐ {int(rewards['xp']):,} XP")
    if rewards.get("gold"):
        reward_lines.append(f"🪙 {int(rewards['gold']):,} Gold")
    if rewards.get("items"):
        reward_lines.append("🎁 Unique Item Reward")
    if rewards.get("reputation"):
        for fid, amt in rewards["reputation"].items():
            faction = FACTIONS.get(fid, {})
            reward_lines.append(f"{faction.get('emoji', '⭐')} +{amt} {faction.get('name', fid)} Rep")
    if reward_lines:
        embed.add_field(name="🏆 Rewards", value="\n".join(reward_lines), inline=True)

    step_text = "\n".join(f"`{i+1}.` {s['objective']}" for i, s in enumerate(next_quest.get("steps") or []))
    if step_text:
        embed.add_field(name="📋 Objectives", value=step_text, inline=False)

    view = QuestOfferView()
    try:
        dm_msg = await dm.send(embed=embed, view=view)
    except Exception:
        await quest_svc.cancel_quest_offer(char_id, qid)
        return web.json_response(_json_safe({"ok": False, "error": "dm_send_failed", "message": "Could not send DM."}), status=500)

    await quest_svc.update_npc_state(char_id, npc_id, "quest_offered")

    # Wait for choice, then apply accept/decline.
    await view.wait()
    if view.choice == "accept":
        await quest_svc.accept_quest(char_id, next_quest["id"])
        accept_embed = _discord.Embed(title="✅ Quest Accepted!", description=next_quest["dialogue"]["accept"], color=0x2ECC71)
        first_step = (next_quest.get("steps") or [{}])[0]
        if first_step.get("objective"):
            accept_embed.add_field(name="📍 First Objective", value=f"{first_step['objective']}\n*{first_step.get('hint','')}*", inline=False)
        await dm_msg.edit(embed=accept_embed, view=None)
        return web.json_response(_json_safe({"ok": True, "message": "Quest accepted in DMs.", "npc_id": npc_id, "quest_id": next_quest["id"]}))
    if view.choice == "decline":
        await quest_svc.cancel_quest_offer(char_id, next_quest["id"])
        decline_embed = _discord.Embed(title="Quest Declined", description=next_quest["dialogue"]["decline"], color=0x95A5A6)
        await dm_msg.edit(embed=decline_embed, view=None)
        return web.json_response(_json_safe({"ok": True, "message": "Quest declined.", "npc_id": npc_id}))

    await quest_svc.cancel_quest_offer(char_id, next_quest["id"])
    return web.json_response(_json_safe({"ok": True, "message": "Interaction ended.", "npc_id": npc_id}))

async def handle_item_equip(request: web.Request) -> web.Response:
    bot = request.app["bot"]
    db = getattr(bot, "db", None)
    if db is None or db.pool is None:
        raise web.HTTPServiceUnavailable(text=json.dumps({"error": "database_unavailable"}), content_type="application/json")

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise web.HTTPUnauthorized(text=json.dumps({"error": "missing_bearer"}), content_type="application/json")
    token = auth_header[7:].strip()
    user = await _discord_user_from_token(token)
    if not user:
        raise web.HTTPUnauthorized(text=json.dumps({"error": "invalid_token"}), content_type="application/json")

    try:
        body = await request.json()
    except json.JSONDecodeError:
        body = {}
    if not isinstance(body, dict):
        body = {}

    item_id = (body.get("item_id") or "").strip()
    if not item_id:
        raise web.HTTPBadRequest(text=json.dumps({"error": "missing_item_id"}), content_type="application/json")

    discord_id = int(user["id"])
    char_svc = CharacterService(db)
    inv_svc = InventoryService(db)
    char = await char_svc.get_character(discord_id)
    if not char:
        return web.json_response({"ok": False, "error": "no_character", "message": "No character found."}, status=400)

    try:
        uid = UUID(item_id)
    except ValueError:
        return web.json_response({"ok": False, "error": "invalid_item_id", "message": "Invalid item id."}, status=400)

    ok, msg = await inv_svc.equip(char["id"], uid)
    status = 200 if ok else 400
    return web.json_response({"ok": ok, "message": msg}, status=status)


async def handle_item_sell(request: web.Request) -> web.Response:
    bot = request.app["bot"]
    db = getattr(bot, "db", None)
    if db is None or db.pool is None:
        raise web.HTTPServiceUnavailable(text=json.dumps({"error": "database_unavailable"}), content_type="application/json")

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise web.HTTPUnauthorized(text=json.dumps({"error": "missing_bearer"}), content_type="application/json")
    token = auth_header[7:].strip()
    user = await _discord_user_from_token(token)
    if not user:
        raise web.HTTPUnauthorized(text=json.dumps({"error": "invalid_token"}), content_type="application/json")

    try:
        body = await request.json()
    except json.JSONDecodeError:
        body = {}
    if not isinstance(body, dict):
        body = {}

    item_id = (body.get("item_id") or "").strip()
    if not item_id:
        raise web.HTTPBadRequest(text=json.dumps({"error": "missing_item_id"}), content_type="application/json")

    discord_id = int(user["id"])
    char_svc = CharacterService(db)
    inv_svc = InventoryService(db)
    char = await char_svc.get_character(discord_id)
    if not char:
        return web.json_response({"ok": False, "error": "no_character", "message": "No character found."}, status=400)

    try:
        uid = UUID(item_id)
    except ValueError:
        return web.json_response({"ok": False, "error": "invalid_item_id", "message": "Invalid item id."}, status=400)

    ok, msg, gold = await inv_svc.sell(char["id"], uid)
    if ok and gold:
        await char_svc.add_gold(char["id"], gold, "vendor sale")
    status = 200 if ok else 400
    return web.json_response({"ok": ok, "message": msg, "gold": gold}, status=status)


async def handle_item_use(request: web.Request) -> web.Response:
    bot = request.app["bot"]
    db = getattr(bot, "db", None)
    if db is None or db.pool is None:
        raise web.HTTPServiceUnavailable(text=json.dumps({"error": "database_unavailable"}), content_type="application/json")

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise web.HTTPUnauthorized(text=json.dumps({"error": "missing_bearer"}), content_type="application/json")
    token = auth_header[7:].strip()
    user = await _discord_user_from_token(token)
    if not user:
        raise web.HTTPUnauthorized(text=json.dumps({"error": "invalid_token"}), content_type="application/json")

    try:
        body = await request.json()
    except json.JSONDecodeError:
        body = {}
    if not isinstance(body, dict):
        body = {}

    item_id = (body.get("item_id") or "").strip()
    if not item_id:
        raise web.HTTPBadRequest(text=json.dumps({"error": "missing_item_id"}), content_type="application/json")

    discord_id = int(user["id"])
    char_svc = CharacterService(db)
    inv_svc = InventoryService(db)
    char = await char_svc.get_character(discord_id)
    if not char:
        return web.json_response({"ok": False, "error": "no_character", "message": "No character found."}, status=400)

    try:
        uid = UUID(item_id)
    except ValueError:
        return web.json_response({"ok": False, "error": "invalid_item_id", "message": "Invalid item id."}, status=400)

    ok, msg, effect = await inv_svc.use_consumable(char["id"], uid)
    if ok and effect:
        effect_type = effect.get("type")
        effect_value = int(effect.get("value", 0) or 0)
        effect_duration = int(effect.get("duration", 0) or 0)

        if effect_type == "heal_hp":
            heal_val = max(effect_value, int(char["max_hp"]) // 4)
            healed = await char_svc.heal(char["id"], heal_val)
            msg += f" Restored {healed} HP."
        elif effect_type == "boost_sta":
            ok2, m2 = await char_svc.boost_stat(char["id"], "sta", effect_value, effect_duration)
            msg = f"{msg} {m2}" if ok2 else m2
            ok = ok2
        elif effect_type == "boost_str":
            ok2, m2 = await char_svc.boost_stat(char["id"], "str", effect_value, effect_duration)
            msg = f"{msg} {m2}" if ok2 else m2
            ok = ok2
        elif effect_type == "boost_agi":
            ok2, m2 = await char_svc.boost_stat(char["id"], "agi", effect_value, effect_duration)
            msg = f"{msg} {m2}" if ok2 else m2
            ok = ok2
        elif effect_type == "boost_int":
            ok2, m2 = await char_svc.boost_stat(char["id"], "int_", effect_value, effect_duration)
            msg = f"{msg} {m2}" if ok2 else m2
            ok = ok2
        elif effect_type == "boost_spi":
            ok2, m2 = await char_svc.boost_stat(char["id"], "spi", effect_value, effect_duration)
            msg = f"{msg} {m2}" if ok2 else m2
            ok = ok2
        elif effect_type == "boost_max_hp":
            ok2, m2 = await char_svc.boost_stat(char["id"], "max_hp", effect_value, effect_duration)
            msg = f"{msg} {m2}" if ok2 else m2
            ok = ok2
        elif effect_type == "boost_resistance":
            ok2, m2 = await char_svc.set_temporary_resistance(char["id"], effect_value, effect_duration)
            msg = f"{msg} {m2}" if ok2 else m2
            ok = ok2

    status = 200 if ok else 400
    return web.json_response({"ok": ok, "message": msg}, status=status)


async def handle_item_unequip(request: web.Request) -> web.Response:
    bot = request.app["bot"]
    db = getattr(bot, "db", None)
    if db is None or db.pool is None:
        raise web.HTTPServiceUnavailable(
            text=json.dumps({"error": "database_unavailable"}), content_type="application/json"
        )

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise web.HTTPUnauthorized(
            text=json.dumps({"error": "missing_bearer"}), content_type="application/json"
        )
    token = auth_header[7:].strip()

    user = await _discord_user_from_token(token)
    if not user:
        raise web.HTTPUnauthorized(
            text=json.dumps({"error": "invalid_token"}), content_type="application/json"
        )

    try:
        body = await request.json()
    except json.JSONDecodeError:
        body = {}
    if not isinstance(body, dict):
        body = {}

    slot = (body.get("slot") or body.get("equip_slot") or "").strip()
    if not slot:
        raise web.HTTPBadRequest(text=json.dumps({"error": "missing_slot"}), content_type="application/json")

    discord_id = int(user["id"])
    char_svc = CharacterService(db)
    inv_svc = InventoryService(db)

    char = await char_svc.get_character(discord_id)
    if not char:
        return web.json_response(
            {"ok": False, "error": "no_character", "message": "No character found."},
            status=400,
        )

    ok, msg = await inv_svc.unequip_slot(char["id"], slot)
    status = 200 if ok else 400
    return web.json_response({"ok": ok, "message": msg}, status=status)


async def handle_item_enhance(request: web.Request) -> web.Response:
    bot = request.app["bot"]
    db = getattr(bot, "db", None)
    if db is None or db.pool is None:
        raise web.HTTPServiceUnavailable(text=json.dumps({"error": "database_unavailable"}), content_type="application/json")

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise web.HTTPUnauthorized(text=json.dumps({"error": "missing_bearer"}), content_type="application/json")
    token = auth_header[7:].strip()
    user = await _discord_user_from_token(token)
    if not user:
        raise web.HTTPUnauthorized(text=json.dumps({"error": "invalid_token"}), content_type="application/json")

    try:
        body = await request.json()
    except json.JSONDecodeError:
        body = {}
    if not isinstance(body, dict):
        body = {}

    item_id = (body.get("item_id") or "").strip()
    protection_type = (body.get("protection_type") or None)
    fragment_count = int(body.get("fragment_count") or 0)
    if not item_id:
        raise web.HTTPBadRequest(text=json.dumps({"error": "missing_item_id"}), content_type="application/json")

    discord_id = int(user["id"])
    char_svc = CharacterService(db)
    char = await char_svc.get_character(discord_id)
    if not char:
        return web.json_response({"ok": False, "error": "no_character", "message": "No character found."}, status=400)

    try:
        uid = UUID(item_id)
    except ValueError:
        return web.json_response({"ok": False, "error": "invalid_item_id", "message": "Invalid item id."}, status=400)

    item = await db.fetchrow(
        """
        SELECT i.id, t.item_type, t.equip_slot, t.name
        FROM inventory i
        JOIN item_templates t ON i.template_id = t.id
        WHERE i.id = $1 AND i.character_id = $2
        """,
        uid,
        char["id"],
    )
    if not item:
        return web.json_response({"ok": False, "error": "item_not_found", "message": "Item not found."}, status=400)
    if not item.get("equip_slot") or item.get("item_type") in ("consumable", "material", "quest"):
        return web.json_response(
            {
                "ok": False,
                "error": "item_not_enhanceable",
                "message": f"{item.get('name', 'This item')} cannot be enhanced.",
            },
            status=400,
        )

    bs = BlacksmithService(db)
    result = await bs.enhance_item(char["id"], uid, protection_type=protection_type, fragment_count=fragment_count)
    ok = bool(result.get("success"))
    status = 200 if ok else 400
    return web.json_response({"ok": ok, **_json_safe(result)}, status=status)


async def handle_health(_request: web.Request) -> web.Response:
    return web.json_response({"ok": True, "service": "world-of-discord-activity-api"})


async def _serve_activity_index(request: web.Request) -> web.StreamResponse:
    """Serve SPA root — aiohttp add_static(show_index=True) lists dirs instead of index.html."""
    root = request.app.get("activity_static_root")
    if not root:
        raise web.HTTPNotFound()
    path = os.path.join(root, "index.html")
    if not os.path.isfile(path):
        raise web.HTTPNotFound(text="activity/dist/index.html missing — run: cd activity && npm run build")
    # Discord can aggressively cache the Activity shell; force revalidation so new hashed bundles load.
    resp = web.FileResponse(path)
    resp.headers["Cache-Control"] = "no-store, max-age=0"
    return resp


async def _serve_activity_item_asset(request: web.Request) -> web.StreamResponse:
    """
    Compatibility: older cached clients may request `/assets/items/<slug>.png` paths.

    We map those to files under `activity/dist/assets/items/` and `.../items/generated/`.
    """
    root = request.app.get("activity_static_root")
    if not root:
        raise web.HTTPNotFound()

    raw = request.match_info.get("name", "")
    name = unquote(raw or "").strip()
    if not name or not name.lower().endswith(".png"):
        raise web.HTTPNotFound()

    assets_root = os.path.join(root, "assets")
    items_root = os.path.join(assets_root, "items")
    gen_root = os.path.join(items_root, "generated")

    # 1) direct match under dist/assets/items/
    direct = os.path.join(items_root, name)
    if os.path.isfile(direct):
        resp = web.FileResponse(direct)
        resp.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return resp

    # 2) map slug to generated root: `health_potion.png` -> `Health Potion.png`
    base = name[:-4]  # strip `.png`
    spaced = base.replace("_", " ").replace("-", " ").strip()
    candidates = [
        f"{spaced}.png",
        f"{spaced.title()}.png",
    ]
    for cand in candidates:
        p = os.path.join(gen_root, cand)
        if os.path.isfile(p):
            resp = web.FileResponse(p)
            resp.headers["Cache-Control"] = "public, max-age=31536000, immutable"
            return resp

    raise web.HTTPNotFound()


def _static_dir() -> Optional[str]:
    env = (os.getenv("ACTIVITY_STATIC_DIR") or "").strip()
    if env and os.path.isdir(env):
        return env
    here = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "activity", "dist"))
    if os.path.isdir(here):
        return here
    return None


async def start_activity_http(bot) -> Optional["web.AppRunner"]:
    """
    Bind HTTP server (OAuth + game JSON). Returns AppRunner for cleanup, or None if disabled.
    """
    if not (os.getenv("DISCORD_CLIENT_SECRET") or "").strip():
        log.info("DISCORD_CLIENT_SECRET not set — Activity HTTP API disabled (set it to enable /api/token).")
        return None

    app = web.Application(middlewares=[cors_middleware])
    app["bot"] = bot

    app.router.add_post("/api/token", handle_token)
    app.router.add_get("/api/game/inventory", handle_inventory)
    app.router.add_get("/api/game/equipment", handle_equipment)
    app.router.add_get("/api/game/progress", handle_progress)
    app.router.add_get("/api/game/map", handle_map)
    app.router.add_get("/api/game/quests", handle_quests)
    app.router.add_get("/api/game/live-events", handle_live_events)
    app.router.add_post("/api/game/travel", handle_travel)
    app.router.add_post("/api/game/explore", handle_explore)
    app.router.add_post("/api/game/npc/interact", handle_npc_interact)
    app.router.add_post("/api/game/item/equip", handle_item_equip)
    app.router.add_post("/api/game/item/unequip", handle_item_unequip)
    app.router.add_post("/api/game/item/sell", handle_item_sell)
    app.router.add_post("/api/game/item/use", handle_item_use)
    app.router.add_post("/api/game/item/enhance", handle_item_enhance)
    app.router.add_get("/api/game/combat/enemies", handle_combat_enemies)
    app.router.add_get("/api/game/combat/state", handle_combat_state)
    app.router.add_post("/api/game/combat/start", handle_combat_start)
    app.router.add_post("/api/game/combat/action", handle_combat_action)
    app.router.add_get("/health", handle_health)

    static_root = _static_dir()
    serve = (os.getenv("ACTIVITY_SERVE_STATIC") or "1").strip().lower() in ("1", "true", "yes")
    if static_root and serve:
        log.info("Serving Activity static files from %s", static_root)
        app["activity_static_root"] = static_root
        # GET / must be index.html — NOT directory listing (show_index=True caused "Index of /")
        app.router.add_get("/", _serve_activity_index)
        # Compatibility route for old cached icon URLs.
        app.router.add_get("/assets/items/{name}", _serve_activity_item_asset)
        assets_dir = os.path.join(static_root, "assets")
        if os.path.isdir(assets_dir):
            app.router.add_static("/assets/", assets_dir, show_index=False)
        else:
            log.warning("No activity/dist/assets — run `cd activity && npm run build` before deploy")

    runner = web.AppRunner(app)
    await runner.setup()

    port = int(os.getenv("PORT", os.getenv("ACTIVITY_HTTP_PORT", "8080")))
    host = os.getenv("ACTIVITY_HTTP_HOST", "0.0.0.0")
    site = web.TCPSite(runner, host, port)
    await site.start()
    log.info(
        "Activity HTTP listening on http://%s:%s (POST /api/token, game inventory + combat API)",
        host,
        port,
    )
    return runner


async def stop_activity_http(runner: Optional["web.AppRunner"]) -> None:
    if runner:
        await runner.cleanup()
