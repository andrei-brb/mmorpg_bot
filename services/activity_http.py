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
  POST /api/game/rest           — Bearer token → full HP/resource restore (rest cooldown; clears iframe combat)
  GET  /api/game/pvp/status     — Bearer token → Arena hub + optional embedded match state
  POST /api/game/pvp/queue      — JSON { mode: casual|ranked }
  DELETE /api/game/pvp/queue    — leave queue / cancel outgoing challenge
  POST /api/game/pvp/challenge  — JSON { target_user_id }
  POST /api/game/pvp/accept     — accept pending challenge
  POST /api/game/pvp/action     — JSON { action, skill_key? }
  GET  /api/game/pvp/history    — ?page=
  GET  /api/game/quests         — Bearer token → active quest log
  POST /api/game/quest/abandon  — JSON { quest_id } → abandon active/offered quest
  GET  /api/game/character/class-options — Public list of playable classes (for create UI)
  POST /api/game/character/create — Bearer JSON { name, class_key, guild_id? } → same shape as GET inventory

Requires DISCORD_CLIENT_SECRET and DISCORD_APPLICATION_ID (same app as the bot).
See ACTIVITY_SETUP.md.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional
from urllib.parse import unquote, urlencode
from uuid import UUID

import aiohttp
from aiohttp import web
import random

from services.character.character_service import CharacterService
from services.character.inventory_service import InventoryService
from services.combat import activity_combat as activity_combat_api
from services.combat import activity_pvp as activity_pvp_api
from services.achievement.achievement_service import AchievementService
from services.blacksmith.blacksmith_service import BlacksmithService
from services.quest.npc_quest_service import NPCQuestService, NPC_TEMPLATES, FACTIONS, get_dynamic_intro, get_rep_level
from config.settings import ZONES, Settings, ENEMIES, SPECIALIZATIONS, CLASSES

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
    allowed = (
        (os.getenv("ACTIVITY_CORS_ORIGINS") or "").strip()
        or (os.getenv("ACTIVITY_ALLOWED_ORIGINS") or "").strip()
    )
    if allowed:
        parts = [x.strip() for x in allowed.split(",") if x.strip()]
        if origin in parts:
            allow_origin = origin
        else:
            # Don't silently allow a different origin; browsers will block this anyway.
            allow_origin = "null"
    else:
        allow_origin = origin if origin else "*"
    return {
        "Access-Control-Allow-Origin": allow_origin,
        "Access-Control-Allow-Methods": "GET, POST, DELETE, OPTIONS",
        "Access-Control-Allow-Headers": "Authorization, Content-Type, X-Guild-Id, X-Guild-ID",
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


def _discord_avatar_url(user: Dict[str, Any], discord_id: int) -> str:
    """Compute a usable Discord CDN avatar URL from the /users/@me payload.

    Returns a fallback embed avatar when no custom avatar is set.
    """
    avatar = user.get("avatar")
    # discriminator may be missing on some tokens; fall back to id modulo if needed
    disc = user.get("discriminator") or user.get("discrim") or "0"
    try:
        disc_int = int(disc) if isinstance(disc, str) and disc.isdigit() else 0
    except Exception:
        disc_int = 0
    if avatar:
        ext = "gif" if str(avatar).startswith("a_") else "png"
        return f"https://cdn.discordapp.com/avatars/{discord_id}/{avatar}.{ext}?size=128"
    # fallback embed avatar (0-4)
    idx = disc_int % 5
    return f"https://cdn.discordapp.com/embed/avatars/{idx}.png"


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
                    "discord": {
                        "id": str(discord_id),
                        "username": user.get("username"),
                        "global_name": user.get("global_name"),
                        "avatar": user.get("avatar"),
                        "avatar_url": _discord_avatar_url(user, discord_id),
                    },
                    "character": None,
                    "items": [],
                }
            )
        )

    items = await inv_svc.get_all(char["id"])
    char_dict = dict(char)
    sk = char_dict.get("specialization")
    if sk:
        spec = SPECIALIZATIONS.get(sk)
        if spec:
            char_dict["specialization_name"] = spec.name
    return web.json_response(
        _json_safe(
            {
                "discord": {
                    "id": str(discord_id),
                    "username": user.get("username"),
                    "global_name": user.get("global_name"),
                    "avatar": user.get("avatar"),
                    "avatar_url": _discord_avatar_url(user, discord_id),
                },
                "character": char_dict,
                "items": items,
            }
        )
    )


async def handle_character_class_options(_request: web.Request) -> web.Response:
    """GET — class keys and display metadata for Activity character creation."""
    classes: List[Dict[str, Any]] = []
    for key, cls in CLASSES.items():
        classes.append(
            {
                "key": key,
                "name": cls.name,
                "emoji": cls.emoji,
                "role": cls.role,
                "resource": cls.resource,
                "description": cls.description[:200],
            }
        )
    return web.json_response({"classes": classes})


async def handle_character_create(request: web.Request) -> web.Response:
    """POST — create first character (same rules as /character create in Discord)."""
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
        raise web.HTTPBadRequest(text=json.dumps({"error": "invalid_json"}), content_type="application/json")
    if not isinstance(body, dict):
        body = {}

    name = body.get("name")
    class_key = body.get("class_key")
    if not isinstance(name, str):
        return web.json_response(
            _json_safe({"ok": False, "error": "invalid_name", "message": "Name is required."}),
            status=400,
        )
    name = name.strip()
    if not (3 <= len(name) <= 32):
        return web.json_response(
            _json_safe({"ok": False, "error": "invalid_name", "message": "Name must be 3–32 characters."}),
            status=400,
        )
    if not isinstance(class_key, str) or class_key not in CLASSES:
        return web.json_response(
            _json_safe({"ok": False, "error": "invalid_class", "message": "Invalid class."}),
            status=400,
        )

    discord_id = int(user["id"])
    display = str(user.get("global_name") or user.get("username") or "unknown")

    char_svc = CharacterService(db)
    inv_svc = InventoryService(db)

    await char_svc.ensure_player(discord_id, display)

    ok, msg, char = await char_svc.create_character(discord_id, name, class_key)
    if not ok or not char:
        return web.json_response(_json_safe({"ok": False, "message": msg}), status=400)

    guild_id = _guild_id_from_request(request, body)
    if guild_id:
        try:
            from services.milestones.milestone_service import MilestoneService

            ms = MilestoneService(bot.db)
            completed = await ms.increment(
                guild_id,
                "characters_created",
                1,
                source="character_create",
                actor_id=discord_id,
            )
            await ms.announce_completions(bot, guild_id, completed)
        except Exception:
            pass

    items = await inv_svc.get_all(char["id"])
    char_dict = dict(char)
    sk = char_dict.get("specialization")
    if sk:
        spec = SPECIALIZATIONS.get(sk)
        if spec:
            char_dict["specialization_name"] = spec.name

    return web.json_response(
        _json_safe(
            {
                "ok": True,
                "discord": {
                    "id": str(discord_id),
                    "username": user.get("username"),
                    "global_name": user.get("global_name"),
                },
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


async def handle_game_dungeons(request: web.Request) -> web.Response:
    """Static dungeon catalog + per-floor enemy preview (aligned with ``config.settings.DUNGEONS``)."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise web.HTTPUnauthorized(text=json.dumps({"error": "missing_bearer"}), content_type="application/json")
    token = auth_header[7:].strip()

    user = await _discord_user_from_token(token)
    if not user:
        raise web.HTTPUnauthorized(text=json.dumps({"error": "invalid_token"}), content_type="application/json")

    from config.settings import DUNGEONS, ENEMIES
    from services.combat.activity_combat import _enemy_key_for_dungeon_floor

    dungeons_out = []
    for dkey, cfg in DUNGEONS.items():
        floor_preview = []
        for f in range(1, cfg.floors + 1):
            ek, is_boss = _enemy_key_for_dungeon_floor(cfg, f)
            t = ENEMIES.get(ek)
            floor_preview.append(
                {
                    "floor": f,
                    "enemy_key": ek,
                    "is_boss": is_boss,
                    "name": t.name if t else ek,
                    "emoji": t.emoji if t else "👾",
                }
            )
        dungeons_out.append(
            {
                "key": dkey,
                "name": cfg.name,
                "emoji": cfg.emoji,
                "description": cfg.description,
                "level_req": cfg.level_req,
                "floors": cfg.floors,
                "xp_per_floor": cfg.xp_reward,
                "gold_min": cfg.gold_reward[0],
                "gold_max": cfg.gold_reward[1],
                "floor_preview": floor_preview,
            }
        )
    return web.json_response(_json_safe({"ok": True, "dungeons": dungeons_out}))


async def handle_dungeon_party_create(request: web.Request) -> web.Response:
    """POST /api/game/dungeon/party/create — Create a dungeon party."""
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

    dungeon_key = body.get("dungeon_key")
    if not dungeon_key or not isinstance(dungeon_key, str):
        return web.json_response({"error": "missing_dungeon_key", "message": "Dungeon key required."}, status=400)

    from config.settings import DUNGEONS
    from services.dungeon.dungeon_service import DungeonService
    from services.character.character_service import CharacterService

    char_svc = CharacterService(db)
    dungeon_svc = DungeonService(db)

    char = await char_svc.get_character(discord_id)
    if not char:
        return web.json_response({"error": "no_character", "message": "Create a character first."}, status=400)

    if char["in_dungeon"]:
        return web.json_response({"error": "already_in_dungeon", "message": "You're already in a dungeon!"}, status=400)

    dungeon_config = DUNGEONS.get(dungeon_key)
    if not dungeon_config:
        return web.json_response({"error": "invalid_dungeon", "message": "Unknown dungeon."}, status=400)

    if char["level"] < dungeon_config.level_req:
        return web.json_response(
            {"error": "level_too_low", "message": f"Requires level {dungeon_config.level_req}+."},
            status=400
        )

    run_id = await dungeon_svc.create_run(dungeon_key, char["id"], is_solo=False)
    if not run_id:
        return web.json_response({"error": "create_failed", "message": "Failed to create party."}, status=500)

    run = await dungeon_svc.get_run(run_id)
    return web.json_response({
        "ok": True,
        "run_id": str(run_id),
        "dungeon": {
            "key": dungeon_key,
            "name": dungeon_config.name,
            "emoji": dungeon_config.emoji,
        },
        "participants": run["participants"],
    })


async def handle_dungeon_party_invite(request: web.Request) -> web.Response:
    """POST /api/game/dungeon/party/invite — Invite a player to the party (leader only)."""
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

    target_user_id = body.get("target_user_id")
    if not target_user_id:
        return web.json_response({"error": "missing_target", "message": "Target user ID required."}, status=400)

    from services.dungeon.dungeon_service import DungeonService
    from services.character.character_service import CharacterService

    char_svc = CharacterService(db)
    dungeon_svc = DungeonService(db)

    char = await char_svc.get_character(discord_id)
    if not char:
        return web.json_response({"error": "no_character", "message": "Create a character first."}, status=400)

    run = await dungeon_svc.get_active_run(char["id"])
    if not run:
        return web.json_response({"error": "not_in_dungeon", "message": "You're not in a dungeon party."}, status=400)

    # Check if leader
    is_leader = any(p["id"] == str(char["id"]) and p.get("role") == "leader" for p in run["participants"])
    if not is_leader:
        return web.json_response({"error": "not_leader", "message": "Only the leader can invite."}, status=403)

    # Get target character
    target_char = await char_svc.get_character(int(target_user_id))
    if not target_char:
        return web.json_response({"error": "target_no_character", "message": "That user has no character."}, status=400)

    if target_char["in_dungeon"]:
        return web.json_response({"error": "target_in_dungeon", "message": "That player is already in a dungeon."}, status=400)

    # Add participant
    success = await dungeon_svc.add_participant(run["id"], target_char["id"])
    if not success:
        return web.json_response({"error": "invite_failed", "message": "Failed to invite player."}, status=500)

    run = await dungeon_svc.get_run(run["id"])
    return web.json_response({
        "ok": True,
        "message": f"Invited {target_char['name']} to the party.",
        "participants": run["participants"],
    })


async def handle_dungeon_party_join(request: web.Request) -> web.Response:
    """POST /api/game/dungeon/party/join — Join a dungeon party by run ID."""
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

    run_id = body.get("run_id")
    if not run_id:
        return web.json_response({"error": "missing_run_id", "message": "Run ID required."}, status=400)

    from uuid import UUID
    from services.dungeon.dungeon_service import DungeonService
    from services.character.character_service import CharacterService

    char_svc = CharacterService(db)
    dungeon_svc = DungeonService(db)

    char = await char_svc.get_character(discord_id)
    if not char:
        return web.json_response({"error": "no_character", "message": "Create a character first."}, status=400)

    if char["in_dungeon"]:
        return web.json_response({"error": "already_in_dungeon", "message": "You're already in a dungeon!"}, status=400)

    try:
        run_id_uuid = UUID(str(run_id))
    except ValueError:
        return web.json_response({"error": "invalid_run_id", "message": "Invalid run ID."}, status=400)

    run = await dungeon_svc.get_run(run_id_uuid)
    if not run:
        return web.json_response({"error": "run_not_found", "message": "Party not found."}, status=404)

    if not run["is_active"]:
        return web.json_response({"error": "run_not_active", "message": "This party is no longer active."}, status=400)

    success = await dungeon_svc.add_participant(run_id_uuid, char["id"])
    if not success:
        return web.json_response({"error": "join_failed", "message": "Failed to join party (may be full)."}, status=400)

    run = await dungeon_svc.get_run(run_id_uuid)
    return web.json_response({
        "ok": True,
        "message": "Joined the party!",
        "run_id": str(run_id),
        "participants": run["participants"],
    })


async def handle_dungeon_party_leave(request: web.Request) -> web.Response:
    """POST /api/game/dungeon/party/leave — Leave the current dungeon party."""
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

    from services.dungeon.dungeon_service import DungeonService
    from services.character.character_service import CharacterService

    char_svc = CharacterService(db)
    dungeon_svc = DungeonService(db)

    char = await char_svc.get_character(discord_id)
    if not char:
        return web.json_response({"error": "no_character", "message": "Create a character first."}, status=400)

    run = await dungeon_svc.get_active_run(char["id"])
    if not run:
        return web.json_response({"error": "not_in_dungeon", "message": "You're not in a dungeon party."}, status=400)

    await dungeon_svc.leave_run(char["id"])
    return web.json_response({"ok": True, "message": "Left the party."})


async def handle_dungeon_party_status(request: web.Request) -> web.Response:
    """GET /api/game/dungeon/party/status — Get current party status."""
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

    from services.dungeon.dungeon_service import DungeonService
    from services.character.character_service import CharacterService

    char_svc = CharacterService(db)
    dungeon_svc = DungeonService(db)

    char = await char_svc.get_character(discord_id)
    if not char:
        return web.json_response({"error": "no_character", "message": "Create a character first."}, status=400)

    run = await dungeon_svc.get_active_run(char["id"])
    if not run:
        return web.json_response({"ok": True, "in_party": False})

    is_leader = any(p["id"] == str(char["id"]) and p.get("role") == "leader" for p in run["participants"])
    return web.json_response({
        "ok": True,
        "in_party": True,
        "run_id": str(run["id"]),
        "is_leader": is_leader,
        "dungeon_key": run["dungeon_key"],
        "participants": run["participants"],
    })


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

    dungeon_key = (body.get("dungeon_key") or "").strip() or None
    floor_raw = body.get("floor")
    enemy_key = (body.get("enemy_key") or body.get("enemy") or "").strip() or None

    force = bool(body.get("force"))
    guild_id = _guild_id_from_request(request, body)

    if dungeon_key and floor_raw is not None:
        try:
            dungeon_floor = int(floor_raw)
        except (TypeError, ValueError):
            raise web.HTTPBadRequest(text=json.dumps({"error": "invalid_floor"}), content_type="application/json")
        result = await activity_combat_api.start_activity_combat(
            bot, discord_id, guild_id, force=force, dungeon_key=dungeon_key, dungeon_floor=dungeon_floor
        )
    elif enemy_key:
        result = await activity_combat_api.start_activity_combat(
            bot, discord_id, guild_id, force=force, enemy_key=enemy_key
        )
    else:
        raise web.HTTPBadRequest(text=json.dumps({"error": "missing_enemy_key"}), content_type="application/json")
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

    ch = {
        "name": char.get("name"),
        "level": char.get("level"),
        "gold": char.get("gold"),
        "last_combat": char.get("last_combat"),
        "class": char.get("class"),
        "specialization": char.get("specialization"),
    }
    if char.get("specialization"):
        sp = SPECIALIZATIONS.get(char["specialization"])
        if sp:
            ch["specialization_name"] = sp.name

    payload = {
        "character": ch,
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


async def handle_specializations(request: web.Request) -> web.Response:
    """GET — specialization choices for Activity (level 10+ prompt)."""
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
        return web.json_response(_json_safe({"ok": False, "error": "no_character"}), status=400)

    c = dict(char)
    class_key = (c.get("class") or "warrior").strip()
    cls_cfg = CLASSES.get(class_key)
    needs = int(c.get("level") or 1) >= Settings.SPEC_UNLOCK_LEVEL and not c.get("specialization")
    options: List[Dict[str, Any]] = []
    if cls_cfg:
        for key in cls_cfg.specializations:
            spec = SPECIALIZATIONS.get(key)
            if spec:
                options.append(
                    {
                        "key": key,
                        "name": spec.name,
                        "emoji": spec.emoji,
                        "role": spec.role,
                        "description": spec.description,
                        "flavor": spec.flavor,
                        "passive_name": spec.passive_name,
                        "passive_desc": spec.passive_desc,
                    }
                )
    return web.json_response(
        _json_safe(
            {
                "ok": True,
                "spec_unlock_level": Settings.SPEC_UNLOCK_LEVEL,
                "needs_choice": needs,
                "class": class_key,
                "specialization": c.get("specialization"),
                "options": options,
            }
        )
    )


async def handle_specialization_choose(request: web.Request) -> web.Response:
    """POST JSON { spec_key } — choose specialization (Activity)."""
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

    spec_key = (body.get("spec_key") or body.get("specialization") or "").strip()
    if not spec_key:
        return web.json_response(
            _json_safe({"ok": False, "error": "missing_spec_key", "message": "Missing spec_key."}),
            status=400,
        )

    discord_id = int(user["id"])
    char_svc = CharacterService(db)
    char = await char_svc.get_character(discord_id)
    if not char:
        return web.json_response(_json_safe({"ok": False, "error": "no_character"}), status=400)

    ok, msg = await char_svc.choose_spec(_uuid_from_any(char["id"]), spec_key)
    if not ok:
        return web.json_response(_json_safe({"ok": False, "message": msg}), status=400)
    return web.json_response(_json_safe({"ok": True, "message": msg, "spec_key": spec_key}))


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


async def handle_rest(request: web.Request) -> web.Response:
    """Full HP/resource restore — same rules as Discord /rest; clears Activity iframe combat if any."""
    _user, discord_id, char, db = await _authed_discord_user_and_char(request)
    if not char:
        return web.json_response(_json_safe({"ok": False, "error": "no_character"}), status=400)

    char_svc = CharacterService(db)
    cd = await char_svc.on_cooldown(_uuid_from_any(char["id"]), "rest")
    if cd:
        return web.json_response(
            _json_safe({"ok": False, "error": "cooldown", "cooldown_s": int(cd)}),
            status=429,
        )

    activity_combat_api.clear_activity_combat_session(discord_id)
    await char_svc.full_restore(_uuid_from_any(char["id"]))
    await char_svc.set_cooldown(_uuid_from_any(char["id"]), "rest", Settings.REST_COOLDOWN)

    fresh = await char_svc.get_character(discord_id)
    if fresh:
        fresh = CharacterService.normalize_resources(dict(fresh))
    return web.json_response(
        _json_safe(
            {
                "ok": True,
                "character": dict(fresh) if fresh else None,
                "rest_cooldown_s": Settings.REST_COOLDOWN,
            }
        )
    )


async def handle_pvp_status(request: web.Request) -> web.Response:
    bot = request.app["bot"]
    try:
        _user, discord_id, char, db = await _authed_discord_user_and_char(request)
    except web.HTTPException:
        raise
    if not char:
        return web.json_response(_json_safe({"match_status": "idle", "error": "no_character"}))
    payload = await activity_pvp_api.build_status_payload(bot, discord_id)
    return web.json_response(_json_safe(payload))


async def handle_pvp_queue_post(request: web.Request) -> web.Response:
    bot = request.app["bot"]
    try:
        _user, discord_id, char, db = await _authed_discord_user_and_char(request)
    except web.HTTPException:
        raise
    if not char:
        return web.json_response(_json_safe({"ok": False, "error": "no_character"}), status=400)
    try:
        body = await request.json()
    except json.JSONDecodeError:
        body = {}
    if not isinstance(body, dict):
        body = {}
    mode = str((body.get("mode") or "casual")).strip().lower()
    if mode not in ("casual", "ranked"):
        mode = "casual"
    guild_id = _guild_id_from_request(request, body)
    r = await activity_pvp_api.join_queue(bot, discord_id, mode, guild_id)
    return web.json_response(_json_safe(r), status=200 if r.get("ok") else 400)


async def handle_pvp_queue_delete(request: web.Request) -> web.Response:
    try:
        _user, discord_id, char, db = await _authed_discord_user_and_char(request)
    except web.HTTPException:
        raise
    if not char:
        return web.json_response(_json_safe({"ok": False, "error": "no_character"}), status=400)
    r = await activity_pvp_api.leave_queue(discord_id)
    return web.json_response(_json_safe(r))


async def handle_pvp_challenge(request: web.Request) -> web.Response:
    bot = request.app["bot"]
    try:
        _user, discord_id, char, db = await _authed_discord_user_and_char(request)
    except web.HTTPException:
        raise
    if not char:
        return web.json_response(_json_safe({"ok": False, "error": "no_character"}), status=400)
    try:
        body = await request.json()
    except json.JSONDecodeError:
        body = {}
    if not isinstance(body, dict):
        body = {}
    target = body.get("target_user_id") or body.get("target")
    if target is None:
        return web.json_response(_json_safe({"ok": False, "error": "missing_target"}), status=400)
    guild_id = _guild_id_from_request(request, body)
    r = await activity_pvp_api.send_challenge(bot, discord_id, str(target), guild_id)
    return web.json_response(_json_safe(r), status=200 if r.get("ok") else 400)


async def handle_pvp_player_search(request: web.Request) -> web.Response:
    """Search players by username prefix for @-autocomplete in PvP hub."""
    try:
        _user, discord_id, char, db = await _authed_discord_user_and_char(request)
    except web.HTTPException:
        raise
    if not char:
        return web.json_response(_json_safe({"ok": False, "error": "no_character", "players": []}), status=400)

    q = str((request.query.get("q") or request.query.get("prefix") or "")).strip()
    if q.startswith("@"):
        q = q[1:].strip()
    if not q:
        return web.json_response(_json_safe({"ok": True, "players": []}))

    q = q[:32]
    rows = await db.fetch(
        """
        SELECT id, username
        FROM players
        WHERE id != $1
          AND username IS NOT NULL
          AND username ILIKE $2
        ORDER BY username ASC
        LIMIT 12
        """,
        discord_id,
        q + "%",
    )
    players = [{"id": str(r["id"]), "username": str(r["username"])} for r in rows if r.get("username")]
    return web.json_response(_json_safe({"ok": True, "players": players}))

async def handle_pvp_accept(request: web.Request) -> web.Response:
    bot = request.app["bot"]
    try:
        _user, discord_id, char, db = await _authed_discord_user_and_char(request)
    except web.HTTPException:
        raise
    if not char:
        return web.json_response(_json_safe({"ok": False, "error": "no_character"}), status=400)
    try:
        body = await request.json()
    except json.JSONDecodeError:
        body = {}
    if not isinstance(body, dict):
        body = {}
    guild_id = _guild_id_from_request(request, body)
    r = await activity_pvp_api.accept_challenge(bot, discord_id, guild_id)
    return web.json_response(_json_safe(r), status=200 if r.get("ok") else 400)


async def handle_pvp_action(request: web.Request) -> web.Response:
    bot = request.app["bot"]
    try:
        _user, discord_id, char, db = await _authed_discord_user_and_char(request)
    except web.HTTPException:
        raise
    if not char:
        return web.json_response(_json_safe({"error": "no_character"}), status=400)
    try:
        body = await request.json()
    except json.JSONDecodeError:
        body = {}
    if not isinstance(body, dict):
        body = {}
    guild_id = _guild_id_from_request(request, body)
    try:
        r = await activity_pvp_api.process_pvp_action(bot, discord_id, guild_id, body)
    except Exception:
        # Unexpected server-side error during PvP action — log full traceback and return 500 JSON
        log.exception("Unhandled exception while processing PvP action for discord_id=%s", discord_id)
        return web.json_response(_json_safe({"error": "server_error", "message": "Internal server error."}), status=500)

    err = r.get("error")
    if err:
        # Treat 'not_your_turn' and 'not_enough_resource' as 409 conflict so client can react specially
        code = 409 if err in ("not_your_turn", "not_enough_resource") else 400
        return web.json_response(_json_safe(r), status=code)
    return web.json_response(_json_safe(r))


async def handle_pvp_history(request: web.Request) -> web.Response:
    bot = request.app["bot"]
    try:
        _user, discord_id, char, db = await _authed_discord_user_and_char(request)
    except web.HTTPException:
        raise
    if not char:
        return web.json_response(_json_safe({"matches": [], "has_more": False, "page": 1}))
    try:
        page = int(request.query.get("page") or "1")
    except (TypeError, ValueError):
        page = 1
    r = await activity_pvp_api.get_history(bot, discord_id, max(1, page))
    return web.json_response(_json_safe(r))


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


async def handle_quest_abandon(request: web.Request) -> web.Response:
    """Abandon an active or offered quest (same effect as Discord /quest abandon)."""
    _user, discord_id, char, db = await _authed_discord_user_and_char(request)
    if not char:
        return web.json_response(_json_safe({"ok": False, "error": "no_character", "message": "No character."}), status=400)

    try:
        body = await request.json()
    except json.JSONDecodeError:
        body = {}
    if not isinstance(body, dict):
        body = {}

    quest_id = (body.get("quest_id") or body.get("questId") or "").strip()
    if not quest_id:
        return web.json_response(
            _json_safe({"ok": False, "error": "missing_quest_id", "message": "Missing quest_id."}),
            status=400,
        )

    qs = NPCQuestService(db)
    char_id = _uuid_from_any(char["id"])
    ok = await qs.abandon_quest(char_id, quest_id)
    if not ok:
        return web.json_response(
            _json_safe(
                {
                    "ok": False,
                    "error": "not_abandoned",
                    "message": "No active or offered quest with that id (already completed or not found).",
                }
            ),
            status=404,
        )
    return web.json_response(_json_safe({"ok": True, "message": "Quest abandoned.", "quest_id": quest_id}))


async def handle_quest_accept(request: web.Request) -> web.Response:
    """Accept a pending quest offer (state='offered')."""
    _user, discord_id, char, db = await _authed_discord_user_and_char(request)
    if not char:
        return web.json_response(_json_safe({"ok": False, "error": "no_character", "message": "No character."}), status=400)
    try:
        body = await request.json()
    except json.JSONDecodeError:
        body = {}
    if not isinstance(body, dict):
        body = {}
    quest_id = str(body.get("quest_id") or body.get("questId") or "").strip()
    if not quest_id:
        return web.json_response(_json_safe({"ok": False, "error": "missing_quest_id", "message": "Missing quest_id."}), status=400)

    qs = NPCQuestService(db)
    char_id = _uuid_from_any(char["id"])
    prog = await qs.get_quest_progress(char_id, quest_id)
    if not prog or prog.get("state") != "offered":
        return web.json_response(_json_safe({"ok": False, "error": "no_offer", "message": "No pending quest offer."}), status=400)
    await qs.accept_quest(char_id, quest_id)
    npc_id = prog.get("npc_id")
    if npc_id:
        await qs.update_npc_state(char_id, str(npc_id), "introduced")
    return web.json_response(_json_safe({"ok": True, "message": "Quest accepted.", "quest_id": quest_id}))


async def handle_quest_decline(request: web.Request) -> web.Response:
    """Decline/ignore a pending quest offer (removes state='offered')."""
    _user, discord_id, char, db = await _authed_discord_user_and_char(request)
    if not char:
        return web.json_response(_json_safe({"ok": False, "error": "no_character", "message": "No character."}), status=400)
    try:
        body = await request.json()
    except json.JSONDecodeError:
        body = {}
    if not isinstance(body, dict):
        body = {}
    quest_id = str(body.get("quest_id") or body.get("questId") or "").strip()
    if not quest_id:
        return web.json_response(_json_safe({"ok": False, "error": "missing_quest_id", "message": "Missing quest_id."}), status=400)

    qs = NPCQuestService(db)
    char_id = _uuid_from_any(char["id"])
    prog = await qs.get_quest_progress(char_id, quest_id)
    if not prog or prog.get("state") != "offered":
        return web.json_response(_json_safe({"ok": False, "error": "no_offer", "message": "No pending quest offer."}), status=400)
    await qs.cancel_quest_offer(char_id, quest_id)
    npc_id = prog.get("npc_id")
    if npc_id:
        await qs.update_npc_state(char_id, str(npc_id), "introduced")
    return web.json_response(_json_safe({"ok": True, "message": "Quest ignored.", "quest_id": quest_id}))

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
    """NPC interaction/quest offer flow (Activity). Returns UI payload (no DMs)."""
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

    # If set after a turn-in, merged into responses (rewards + next DM offer).
    pending_completion: Optional[Dict[str, Any]] = None

    def _merge_completion_payload(base: Dict[str, Any]) -> Dict[str, Any]:
        if not pending_completion:
            return base
        return {**pending_completion, **base}

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
        pending_completion = {
            "quest_completed": True,
            "rewards": reward_summary,
            "message": "Quest completed and rewards granted.",
        }
        char_row = await char_svc.get_by_id(char_id)
        if char_row:
            char = dict(char_row)

        if not next_quest:
            return web.json_response(
                _json_safe(
                    _merge_completion_payload(
                        {
                            "ok": True,
                            "npc_id": npc_id,
                            "next_quest_available": False,
                        }
                    )
                )
            )
        if int(char.get("level") or 1) < int(next_quest.get("level_req", 1) or 1):
            return web.json_response(
                _json_safe(
                    _merge_completion_payload(
                        {
                            "ok": True,
                            "npc_id": npc_id,
                            "next_quest_available": True,
                            "next_quest_blocked": "level_too_low",
                            "message": f"Quest complete. Next quest needs level {next_quest['level_req']}.",
                        }
                    )
                )
            )
        # Continue below: automatically send the next quest offer via DM (same as Interact).
    elif talk_result and not talk_result.get("complete"):
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
    else:
        # No talk turn-in on this click — offer the next available quest for this NPC.
        completed_quest_ids = [q["quest_id"] for q in await quest_svc.get_completed_quests(char_id)]
        next_quest = quest_svc.get_next_quest_for_npc(npc_id, completed_quest_ids)
        if not next_quest:
            return web.json_response(_json_safe({"ok": True, "message": "No quests available.", "npc_id": npc_id}))

        # Level requirement
        if int(char.get("level") or 1) < int(next_quest.get("level_req", 1) or 1):
            return web.json_response(
                _json_safe({"ok": False, "error": "level_too_low", "message": f"Need level {next_quest['level_req']}."}),
                status=400,
            )

    # `next_quest` is set (from completion chain or from branch above). Offer via DM.

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
                    _merge_completion_payload(
                        {
                            "ok": False,
                            "error": "quest_already_active",
                            "message": "You already have this quest active. Finish it (or abandon) before taking a new offer.",
                        }
                    )
                ),
                status=400,
            )
        if prog and prog.get("state") == "offered":
            return web.json_response(
                _json_safe(
                    _merge_completion_payload(
                        {
                            "ok": False,
                            "error": "quest_offer_pending",
                            "message": "You already have a pending quest offer — check your DMs.",
                        }
                    )
                ),
                status=400,
            )
        return web.json_response(
            _json_safe(
                _merge_completion_payload({"ok": False, "error": "quest_unavailable", "message": "Could not start quest offer."})
            ),
            status=400,
        )

    char_class = char.get("class", "warrior")
    char_level = int(char.get("level") or 1)
    intro_text = get_dynamic_intro(npc_id, npc_data, char_class, char_level)

    rewards = next_quest.get("rewards", {}) or {}
    reward_summary = {
        "xp": int(rewards.get("xp") or 0),
        "gold": int(rewards.get("gold") or 0),
        "items": list(rewards.get("items") or []),
        "reputation": {k: int(v) for k, v in (rewards.get("reputation") or {}).items()},
    }
    objectives = [
        {"objective": s.get("objective"), "hint": s.get("hint")}
        for s in (next_quest.get("steps") or [])
        if isinstance(s, dict)
    ]

    await quest_svc.update_npc_state(char_id, npc_id, "quest_offered")
    body: Dict[str, Any] = {
        "ok": True,
        "message": "Quest offer ready.",
        "npc_id": npc_id,
        "quest_offered": True,
        "offer": {
            "npc_id": npc_id,
            "npc_name": npc_data.get("name"),
            "npc_title": npc_data.get("title"),
            "intro": intro_text,
            "quest_id": next_quest.get("id"),
            "quest_name": next_quest.get("name"),
            "quest_desc": next_quest.get("description"),
            "level_req": int(next_quest.get("level_req") or 1),
            "time_limit_hours": next_quest.get("time_limit_hours"),
            "rewards": reward_summary,
            "objectives": objectives,
            "dialogue": {
                "accept": (next_quest.get("dialogue") or {}).get("accept"),
                "decline": (next_quest.get("dialogue") or {}).get("decline"),
            },
        },
    }
    return web.json_response(_json_safe(_merge_completion_payload(body)))

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
    if not ok:
        try:
            log.warning(
                "enhance rejected: char=%s item=%s prot=%s frags=%s msg=%s",
                str(char.get("id")),
                str(uid),
                str(protection_type),
                str(fragment_count),
                str(result.get("message") or result),
            )
        except Exception:
            pass
    return web.json_response({"ok": ok, **_json_safe(result)}, status=status)


async def handle_item_enhance_info(request: web.Request) -> web.Response:
    """Return enhancement preview + available protection items (Activity modal)."""
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

    item_id = (request.query.get("item_id") or "").strip()
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

    bs = BlacksmithService(db)
    info = await bs.get_enhancement_info(uid, char["id"])
    if not info:
        return web.json_response({"ok": False, "error": "item_not_found", "message": "Item not found."}, status=404)

    protections = await bs.get_protection_inventory(char["id"])
    return web.json_response(
        _json_safe(
            {
                "ok": True,
                "info": info,
                "protections": protections,
            }
        )
    )


async def handle_buy_protection(request: web.Request) -> web.Response:
    """Buy protection items for enhancement (Activity modal convenience)."""
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

    key = (body.get("protection_key") or body.get("key") or "").strip()
    qty = int(body.get("quantity") or 1)
    if not key:
        return web.json_response({"ok": False, "error": "missing_key", "message": "Missing protection_key."}, status=400)

    discord_id = int(user["id"])
    char_svc = CharacterService(db)
    char = await char_svc.get_character(discord_id)
    if not char:
        return web.json_response({"ok": False, "error": "no_character", "message": "No character found."}, status=400)

    bs = BlacksmithService(db)
    ok, msg = await bs.buy_protection_bulk(_uuid_from_any(char["id"]), key, qty)
    status = 200 if ok else 400
    return web.json_response(_json_safe({"ok": ok, "message": msg}), status=status)

async def handle_health(_request: web.Request) -> web.Response:
    return web.json_response({"ok": True, "service": "world-of-discord-activity-api"})


def _deployed_version() -> dict:
    """Best-effort deployed version info for debugging hosting issues."""
    return {
        "git_sha": (os.getenv("RAILWAY_GIT_COMMIT_SHA") or os.getenv("GIT_SHA") or "").strip() or None,
        "railway_service": (os.getenv("RAILWAY_SERVICE_NAME") or "").strip() or None,
        "railway_environment": (os.getenv("RAILWAY_ENVIRONMENT_NAME") or "").strip() or None,
        "activity_public_url": (os.getenv("ACTIVITY_PUBLIC_URL") or "").strip() or None,
        "discord_oauth_redirect_uri": (os.getenv("DISCORD_OAUTH_REDIRECT_URI") or "").strip() or None,
        "has_discord_client_secret": bool((os.getenv("DISCORD_CLIENT_SECRET") or "").strip()),
    }


async def handle_meta(request: web.Request) -> web.Response:
    """
    Debug endpoint: shows backend host + version + oauth redirect config.
    Safe to expose because it does not return secrets, only presence/strings.
    """
    host = request.headers.get("Host")
    proto = request.headers.get("X-Forwarded-Proto") or request.scheme
    base = f"{proto}://{host}" if host else None
    return web.json_response({"ok": True, "backend_base_url": base, **_deployed_version()})


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
    app.router.add_get("/api/game/character/class-options", handle_character_class_options)
    app.router.add_post("/api/game/character/create", handle_character_create)
    app.router.add_get("/api/game/equipment", handle_equipment)
    app.router.add_get("/api/game/progress", handle_progress)
    app.router.add_get("/api/game/specializations", handle_specializations)
    app.router.add_post("/api/game/character/specialization", handle_specialization_choose)
    app.router.add_get("/api/game/map", handle_map)
    app.router.add_get("/api/game/quests", handle_quests)
    app.router.add_post("/api/game/quest/abandon", handle_quest_abandon)
    app.router.add_post("/api/game/quest/accept", handle_quest_accept)
    app.router.add_post("/api/game/quest/decline", handle_quest_decline)
    app.router.add_get("/api/game/live-events", handle_live_events)
    app.router.add_post("/api/game/travel", handle_travel)
    app.router.add_post("/api/game/explore", handle_explore)
    app.router.add_post("/api/game/npc/interact", handle_npc_interact)
    app.router.add_post("/api/game/item/equip", handle_item_equip)
    app.router.add_post("/api/game/item/unequip", handle_item_unequip)
    app.router.add_post("/api/game/item/sell", handle_item_sell)
    app.router.add_post("/api/game/item/use", handle_item_use)
    app.router.add_post("/api/game/item/enhance", handle_item_enhance)
    app.router.add_get("/api/game/item/enhance/info", handle_item_enhance_info)
    app.router.add_post("/api/game/blacksmith/buy-protection", handle_buy_protection)
    app.router.add_get("/api/game/combat/enemies", handle_combat_enemies)
    app.router.add_get("/api/game/dungeons", handle_game_dungeons)
    app.router.add_get("/api/game/dungeon/party/status", handle_dungeon_party_status)
    app.router.add_post("/api/game/dungeon/party/create", handle_dungeon_party_create)
    app.router.add_post("/api/game/dungeon/party/invite", handle_dungeon_party_invite)
    app.router.add_post("/api/game/dungeon/party/join", handle_dungeon_party_join)
    app.router.add_post("/api/game/dungeon/party/leave", handle_dungeon_party_leave)
    app.router.add_get("/api/game/combat/state", handle_combat_state)
    app.router.add_post("/api/game/combat/start", handle_combat_start)
    app.router.add_post("/api/game/combat/action", handle_combat_action)
    app.router.add_post("/api/game/rest", handle_rest)
    app.router.add_get("/api/game/pvp/status", handle_pvp_status)
    app.router.add_post("/api/game/pvp/queue", handle_pvp_queue_post)
    app.router.add_delete("/api/game/pvp/queue", handle_pvp_queue_delete)
    app.router.add_post("/api/game/pvp/challenge", handle_pvp_challenge)
    app.router.add_get("/api/game/pvp/players", handle_pvp_player_search)
    app.router.add_post("/api/game/pvp/accept", handle_pvp_accept)
    app.router.add_post("/api/game/pvp/action", handle_pvp_action)
    app.router.add_get("/api/game/pvp/history", handle_pvp_history)
    app.router.add_get("/health", handle_health)
    app.router.add_get("/api/meta", handle_meta)

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
        # Vite copies `activity/public/textures/` → `dist/textures/` (CSS uses url('/textures/...')).
        textures_dir = os.path.join(static_root, "textures")
        if os.path.isdir(textures_dir):
            app.router.add_static("/textures/", textures_dir, show_index=False)
        else:
            log.warning("No activity/dist/textures — UI panel backgrounds may 404")
        # Combat skill bar: `public/skills/skill_<key>.png` → `/skills/...` (see `activity/src/lib/skillIconUrl.ts`).
        skills_dir = os.path.join(static_root, "skills")
        if os.path.isdir(skills_dir):
            app.router.add_static("/skills/", skills_dir, show_index=False)
        else:
            log.warning("No activity/dist/skills — run `cd activity && npm run build`; combat skill icons may 404")

        # Character class/spec icons: `public/classes/*` + `public/specs/*` → `/classes/...` + `/specs/...`
        classes_dir = os.path.join(static_root, "classes")
        if os.path.isdir(classes_dir):
            app.router.add_static("/classes/", classes_dir, show_index=False)
        else:
            log.warning("No activity/dist/classes — run `cd activity && npm run build`; class icons may 404")

        specs_dir = os.path.join(static_root, "specs")
        if os.path.isdir(specs_dir):
            app.router.add_static("/specs/", specs_dir, show_index=False)
        else:
            log.warning("No activity/dist/specs — run `cd activity && npm run build`; spec icons may 404")

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
