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
from urllib.parse import urlencode
from uuid import UUID

import aiohttp
from aiohttp import web

from services.character.character_service import CharacterService
from services.character.inventory_service import InventoryService
from services.combat import activity_combat as activity_combat_api
from services.achievement.achievement_service import AchievementService

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
    return web.FileResponse(path)


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
