"""
╔══════════════════════════════════════════════════════════════════════════════╗
║   services/activity_http.py — HTTP API for Discord Embedded App (Activity)  ║
╚══════════════════════════════════════════════════════════════════════════════╝

Endpoints:
  POST /api/token              — Exchange OAuth code (from Embedded App SDK) for access_token
  GET  /api/game/inventory     — Bearer token → character + inventory rows
  GET  /api/game/equipment     — Bearer token → equipped items by slot
  GET  /api/game/combat/enemies — Bearer token → enemies/bosses (current zone; optional ?zone_key= for preview)
  GET  /api/game/combat/state   — Bearer token → active iframe combat (if any)
  POST /api/game/combat/start  — JSON { enemy_key, guild_id?, force? }
  POST /api/game/combat/action — JSON { ability, flee?, potion?, guild_id? }
  POST /api/game/rest           — Bearer token → full HP/resource restore (rest cooldown; clears iframe combat)
  GET  /api/game/idle/rewards  — Bearer token → pending offline XP/gold (capped window; preview only)
  POST /api/game/idle/claim    — Bearer JSON { guild_id? } → award pending rewards, reset accrual timer
  POST /api/game/guild/checkin     — POST daily hall check-in (gold + XP + guild XP; UTC day)
  GET  /api/game/guild/me           — Bearer → in-guild snapshot (bank, boss, tech, raids)
  POST /api/game/guild/create      — JSON { name, tag?, guild_id? } — found a guild (needs X-Guild-Id / guild_id = Discord server)
  POST /api/game/guild/bank/deposit — JSON { amount }
  POST /api/game/guild/bank/withdraw — JSON { amount } (officer/guildmaster)
  GET  /api/game/guild/feed         — ?cursor=uuid
  POST /api/game/guild/feed         — JSON { body }
  POST /api/game/guild/boss/start   — JSON { boss_key? }
  POST /api/game/guild/boss/hit     — JSON { encounter_id? }
  POST /api/game/guild/tech/unlock  — JSON { node_id }
  POST /api/game/guild/raid/create  — JSON { template_key? }
  POST /api/game/guild/raid/signup  — JSON { run_id }
  POST /api/game/guild/raid/start   — JSON { run_id }
  POST /api/game/guild/raid/complete — JSON { run_id }
  GET  /api/game/guild/invite/candidates — ?q= prefix search (officer/guildmaster; character names)
  POST /api/game/guild/invite/send — JSON { target_character_id } → DM invite (same as /guild invite)
  GET  /api/game/pvp/status     — Bearer token → Arena hub + optional embedded match state
  POST /api/game/pvp/queue      — JSON { mode: casual|ranked }
  DELETE /api/game/pvp/queue    — leave queue / cancel outgoing challenge
  POST /api/game/pvp/challenge  — JSON { target_user_id }
  POST /api/game/pvp/accept     — accept pending challenge
  POST /api/game/pvp/action     — JSON { action, skill_key? }
  GET  /api/game/pvp/history    — ?page=
  GET  /api/game/quests         — Bearer token → active quest log
  GET  /api/game/deeds          — Bearer token → story deed flags (Obsidian / lore progression)
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
import time
from collections import defaultdict, deque
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Deque, Dict, List, Optional, Tuple
from urllib.parse import unquote, urlencode
from uuid import UUID

import aiohttp
import discord
from aiohttp import web
import random

from services.character.character_service import CharacterService
from services.character.inventory_service import InventoryService
from services.market_auction import (
    auction_min_bid,
    maybe_extend_auction_end,
    settle_expired_auctions,
)
from services.combat import activity_combat as activity_combat_api
from services.combat import activity_pvp as activity_pvp_api
from services.achievement.achievement_service import AchievementService
from services.blacksmith.blacksmith_service import BlacksmithService
from services.crafting.crafting_service import CraftingService
from services.lore.lore_gate_service import LoreGateService
from services.quest.npc_quest_service import (
    NPCQuestService,
    NPC_TEMPLATES,
    FACTIONS,
    get_dynamic_intro,
    get_rep_level,
    is_main_story_quest,
)
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


def _is_production_deploy() -> bool:
    env = (os.getenv("ENV") or "").strip().lower()
    if env in ("production", "prod"):
        return True
    return bool((os.getenv("RAILWAY_ENVIRONMENT") or "").strip())


def _dev_origin_allowed(origin: str) -> bool:
    if not origin:
        return False
    low = origin.lower()
    return (
        low.startswith("http://localhost")
        or low.startswith("https://localhost")
        or low.startswith("http://127.0.0.1")
        or low.startswith("https://127.0.0.1")
    )


# Capacitor/native mobile WebView origins. The mobile app makes DIRECT
# cross-origin requests to this API (the Discord Activity instead proxies
# same-origin via Vercel), so these must always be allowed for cross-play.
_NATIVE_APP_ORIGINS = frozenset(
    {"capacitor://localhost", "ionic://localhost", "http://localhost", "https://localhost"}
)


def _cors_headers(request: web.Request) -> Dict[str, str]:
    origin = request.headers.get("Origin", "")
    allowed = (
        (os.getenv("ACTIVITY_CORS_ORIGINS") or "").strip()
        or (os.getenv("ACTIVITY_ALLOWED_ORIGINS") or "").strip()
    )
    if origin in _NATIVE_APP_ORIGINS:
        allow_origin = origin
    elif allowed:
        parts = [x.strip() for x in allowed.split(",") if x.strip()]
        if origin in parts:
            allow_origin = origin
        else:
            allow_origin = "null"
    elif _dev_origin_allowed(origin):
        allow_origin = origin
    elif _is_production_deploy():
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
    except Exception as e:
        # A non-HTTP exception would otherwise become a bare aiohttp 500 with
        # no CORS headers, which a cross-origin (capacitor://localhost) client
        # sees as an opaque "Load failed" TypeError. Attach CORS and surface a
        # readable JSON 500 instead — and log the traceback so the real cause
        # is visible.
        log.exception("activity_http handler crashed: %s %s", request.method, request.path)
        resp = web.HTTPInternalServerError(
            text=json.dumps({"ok": False, "error": "internal_error"}),
            content_type="application/json",
        )
        resp.headers.update(_cors_headers(request))
        raise resp
    for k, v in _cors_headers(request).items():
        response.headers.setdefault(k, v)
    return response


_TOKEN_USER_CACHE: Dict[str, Tuple[int, float]] = {}
_RATE_BUCKETS: Dict[int, Deque[float]] = defaultdict(deque)
_RATE_WINDOW_S = 60.0


def _rate_limit_per_min() -> int:
    try:
        return max(10, int(os.getenv("ACTIVITY_RATE_LIMIT_PER_MIN", "90")))
    except ValueError:
        return 90


async def _rate_limit_player_id(token: str) -> Optional[int]:
    """Player id for rate-limit bucketing. Our own session JWT verifies locally
    (no network); otherwise fall back to the cached Discord `/users/@me` lookup."""
    from services.auth.session_tokens import verify_session

    claims = verify_session(token)
    if claims is not None:
        return int(claims["sub"])

    now = time.time()
    cached = _TOKEN_USER_CACHE.get(token)
    if cached and cached[1] > now:
        return cached[0]
    du = await _discord_user_from_token(token)
    if not du:
        return None
    uid = int(du["id"])
    _TOKEN_USER_CACHE[token] = (uid, now + 60.0)
    if len(_TOKEN_USER_CACHE) > 5000:
        expired = [k for k, v in _TOKEN_USER_CACHE.items() if v[1] <= now]
        for k in expired[:2500]:
            _TOKEN_USER_CACHE.pop(k, None)
    return uid


def _rate_limit_retry_after_s(user_id: int) -> Optional[int]:
    limit = _rate_limit_per_min()
    now = time.monotonic()
    bucket = _RATE_BUCKETS[user_id]
    while bucket and bucket[0] <= now - _RATE_WINDOW_S:
        bucket.popleft()
    if len(bucket) >= limit:
        wait = int(_RATE_WINDOW_S - (now - bucket[0])) + 1
        return max(1, wait)
    bucket.append(now)
    return None


# ── Auth throttling ──────────────────────────────────────────────────────────
# Separate from the gameplay limiter above, and deliberately unlike it.
#
# That one buckets by players.id and FAILS OPEN (:263-266 below) — correct for
# gameplay, where an unresolvable token just means the handler will 401 anyway.
# For login it would be a hole: no token exists yet, so every request would skip
# the limiter and password guessing would be unlimited.
#
# So: bucket by client IP, and fail CLOSED. The handlers add a second bucket per
# login identifier (see _auth_login_throttle) because one attacker rotating IPs
# against one account, and one IP spraying many accounts, are different attacks
# and neither bucket catches both.
_AUTH_IP_BUCKETS: Dict[str, Deque[float]] = defaultdict(deque)
_AUTH_LOGIN_BUCKETS: Dict[str, Deque[float]] = defaultdict(deque)
_AUTH_WINDOW_S = 900.0  # 15 minutes
_AUTH_IP_MAX = 30       # attempts per IP per window
_AUTH_LOGIN_MAX = 8     # attempts per username/email per window


def _client_ip(request: web.Request) -> str:
    """Client IP, honouring the proxy header Railway sets.

    X-Forwarded-For is client-controllable in general; we take the FIRST entry
    because that is what the edge proxy prepends. Worst case a determined
    attacker spreads their guesses, which is exactly why the per-login bucket
    exists alongside this one.
    """
    xff = request.headers.get("X-Forwarded-For", "")
    if xff:
        return xff.split(",")[0].strip()
    peer = request.remote or ""
    return peer or "unknown"


def _bucket_retry_after(buckets: Dict[str, Deque[float]], key: str, limit: int) -> Optional[int]:
    now = time.monotonic()
    b = buckets[key]
    while b and b[0] <= now - _AUTH_WINDOW_S:
        b.popleft()
    if len(b) >= limit:
        return max(1, int(_AUTH_WINDOW_S - (now - b[0])) + 1)
    b.append(now)
    return None


def _auth_login_throttle(login: str) -> Optional[int]:
    """Per-account attempt bucket. Call from login/forgot once the body is read."""
    key = (login or "").strip().lower()
    if not key:
        return None
    return _bucket_retry_after(_AUTH_LOGIN_BUCKETS, key, _AUTH_LOGIN_MAX)


def _rate_limited_response(request: web.Request, retry: int) -> web.Response:
    return web.Response(
        status=429,
        text=json.dumps({"ok": False, "error": "rate_limited", "retry_after_s": retry}),
        content_type="application/json",
        headers=_cors_headers(request),
    )


@web.middleware
async def rate_limit_middleware(request: web.Request, handler):
    if request.method == "OPTIONS":
        return await handler(request)
    path = request.path or ""

    # Auth endpoints: throttle by IP before the handler ever sees a password.
    # Only the credential-checking routes — /link/* are session-authenticated and
    # ride the gameplay limiter instead.
    if path.startswith("/api/auth/"):
        retry = _bucket_retry_after(_AUTH_IP_BUCKETS, _client_ip(request), _AUTH_IP_MAX)
        if retry is not None:
            return _rate_limited_response(request, retry)
        return await handler(request)

    if not path.startswith("/api/game/"):
        return await handler(request)
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return await handler(request)
    token = auth_header[7:].strip()
    if not token:
        return await handler(request)
    try:
        user_id = await _rate_limit_player_id(token)
    except Exception:
        return await handler(request)
    if user_id is None:
        return await handler(request)
    retry = _rate_limit_retry_after_s(user_id)
    if retry is not None:
        return web.Response(
            status=429,
            text=json.dumps({"error": "rate_limited", "retry_after_s": retry}),
            content_type="application/json",
            headers=_cors_headers(request),
        )
    return await handler(request)


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


def _redirect_uri_variants(url: str) -> list[str]:
    """Discord matches redirect_uri exactly; try with and without trailing slash."""
    u = (url or "").strip()
    if not u:
        return []
    base = u.rstrip("/")
    out: list[str] = []
    for c in (base + "/", base):
        if c not in out:
            out.append(c)
    return out


def _oauth_redirect_attempts(explicit: Optional[str] = None) -> list[Optional[str]]:
    """
    Discord token exchange: redirect_uri must match OAuth2 → Redirects when sent.

    Order:
    1) Variants of `explicit` from the Activity (`window.location.origin` on discordsays.com)
       — usually the correct string for Embedded Activities.
    2) Omit `redirect_uri` — some Embedded flows match Discord examples (`code` only).
    3) DISCORD_OAUTH_REDIRECT_URI or ACTIVITY_PUBLIC_URL if set.

    Callers cap how many attempts run; repeating failed exchanges with the same code can yield
    invalid_grant if the code is single-use.
    """
    seen: set[str | None] = set()
    out: list[Optional[str]] = []

    def add(x: Optional[str]) -> None:
        if x in seen:
            return
        seen.add(x)
        out.append(x)

    for c in _redirect_uri_variants((explicit or "").strip()):
        add(c)
    add(None)
    raw = (os.getenv("DISCORD_OAUTH_REDIRECT_URI") or os.getenv("ACTIVITY_PUBLIC_URL") or "").strip()
    for c in _redirect_uri_variants(raw):
        add(c)
    return out


# Max POSTs per code exchange — Discord may invalidate the code after a failed attempt.
_OAUTH_REDIRECT_MAX_ATTEMPTS = 3


async def _exchange_oauth_code(
    code: str,
    client_id: str,
    client_secret: str,
    redirect_uri_hint: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Exchange authorization code for tokens. Discord may require redirect_uri to match
    Developer Portal → OAuth2 → Redirects (same string as Activity public URL).
    """
    timeout = aiohttp.ClientTimeout(total=20)
    last_body = ""
    last_status = 0

    attempts = _oauth_redirect_attempts(redirect_uri_hint)[:_OAUTH_REDIRECT_MAX_ATTEMPTS]
    for attempt_idx, redirect_uri in enumerate(attempts):
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

                err_lower = text.lower()
                can_retry = attempt_idx < len(attempts) - 1 and (
                    "redirect" in err_lower or "invalid_grant" in err_lower
                )
                if can_retry:
                    log.warning(
                        "OAuth token exchange failed (%s) with redirect_uri=%r: %s",
                        resp.status,
                        redirect_uri,
                        text[:300],
                    )
                    continue
                break

    log.warning("OAuth token exchange failed: %s %s", last_status, last_body[:500])

    discord_err = ""
    discord_desc = ""
    try:
        errj = json.loads(last_body)
        if isinstance(errj, dict):
            discord_err = str(errj.get("error") or "")
            discord_desc = str(errj.get("error_description") or "")
    except Exception:
        pass

    hint_parts = [
        "Token exchange redirect_uri must match Developer Portal → OAuth2 → Redirects "
        "for the URL where the Activity runs (e.g. https://YOUR_APPLICATION_ID.discordsays.com/). "
        "List both with and without a trailing slash if unsure.",
        "Railway: DISCORD_APPLICATION_ID must match the same Application ID as VITE_DISCORD_CLIENT_ID in your built Activity.",
        "Use the OAuth2 Client Secret from the same app (Developer Portal → OAuth2), not the bot token.",
    ]
    if "invalid_client" in (discord_err + last_body).lower():
        hint_parts.insert(
            0,
            "invalid_client usually means wrong OAuth2 client secret or wrong client_id.",
        )
    if discord_err == "invalid_grant" or "invalid_grant" in last_body.lower():
        hint_parts.append(
            "invalid_grant often means redirect_uri mismatch, expired code, or the code was already used "
            "(e.g. React Strict Mode double-mount in dev). Try a production build or a single page load.",
        )

    raise web.HTTPBadRequest(
        text=json.dumps(
            {
                "error": "token_exchange_failed",
                "detail": last_body[:400],
                "discord_error": discord_err or None,
                "discord_error_description": discord_desc or None,
                "hint": " ".join(hint_parts),
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

    redirect_hint = (body or {}).get("redirect_uri")
    if redirect_hint is not None and not isinstance(redirect_hint, str):
        redirect_hint = None
    if isinstance(redirect_hint, str):
        redirect_hint = redirect_hint.strip() or None

    token_payload = await _exchange_oauth_code(code, client_id, secret, redirect_hint)
    access_token = token_payload.get("access_token")
    if not access_token:
        raise web.HTTPBadRequest(
            text=json.dumps({"error": "no_access_token"}),
            content_type="application/json",
        )
    return web.json_response({"access_token": access_token})


async def handle_auth_mobile_callback(request: web.Request) -> web.Response:
    """OAuth bounce page for the mobile app.

    Discord only accepts http(s) redirect URIs, not custom schemes. The mobile
    app registers THIS https URL as its Discord redirect; after login Discord
    sends the browser here with ?code=..., and this page immediately forwards to
    the app's custom-scheme deep link (com.wold.mmo://auth/discord?code=...),
    which iOS/Android route back into the app.
    """
    qs = request.query_string
    deep_link = "com.wold.mmo://auth/discord" + (("?" + qs) if qs else "")
    dl_js = json.dumps(deep_link)
    html = (
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<title>Signing in…</title>"
        f"<script>location.replace({dl_js});</script></head>"
        "<body style='background:#0b0b0f;color:#cbb680;font-family:-apple-system,system-ui,sans-serif;"
        "text-align:center;padding-top:30vh'>"
        "<p>Returning to the game…</p>"
        f"<p><a href={dl_js} style='color:#cbb680'>Tap here if it doesn't open automatically</a></p>"
        "</body></html>"
    )
    return web.Response(text=html, content_type="text/html", headers=_cors_headers(request))


async def handle_auth_discord_exchange(request: web.Request) -> web.Response:
    """Standalone Discord login (mobile / standalone web): exchange a Discord
    OAuth code for OUR session JWT, so the client authenticates without the
    embedded Discord host and without a Discord round-trip per request.

    Cross-play: the resulting player is keyed on the Discord user id exactly like
    the embedded Activity, so it's the same character/world.
    """
    bot = request.app["bot"]
    db = getattr(bot, "db", None)
    if db is None or db.pool is None:
        raise web.HTTPServiceUnavailable(text=json.dumps({"error": "database_unavailable"}), content_type="application/json")
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
    redirect_hint = (body or {}).get("redirect_uri")
    redirect_hint = redirect_hint.strip() if isinstance(redirect_hint, str) and redirect_hint.strip() else None

    token_payload = await _exchange_oauth_code(code, client_id, secret, redirect_hint)
    discord_token = token_payload.get("access_token")
    if not discord_token:
        raise web.HTTPBadRequest(text=json.dumps({"error": "no_access_token"}), content_type="application/json")

    du = await _discord_user_from_token(discord_token)
    if not du:
        raise web.HTTPUnauthorized(text=json.dumps({"error": "invalid_token"}), content_type="application/json")

    discord_id = int(du["id"])
    char_svc = CharacterService(db)
    await char_svc.ensure_player(discord_id, du.get("username") or du.get("global_name") or f"user{discord_id}")

    from services.auth.session_tokens import issue_session

    session_jwt = issue_session(
        discord_id,
        "discord",
        identity={
            "username": du.get("username"),
            "global_name": du.get("global_name"),
            "avatar": du.get("avatar"),
        },
    )

    # Record the identity so this Discord account resolves through the same
    # table as a game account. Existing players were backfilled at boot
    # (database/db.py, initialize_schema tail); this covers anyone new.
    try:
        from services.auth.identities import PROVIDER_DISCORD, link_identity

        await link_identity(db, PROVIDER_DISCORD, str(discord_id), discord_id)
    except Exception as e:
        # Never fail a working login over bookkeeping — resolution for Discord
        # still works off players.id today.
        log.warning("link discord identity failed for %s: %s", discord_id, e)

    return web.json_response({"access_token": session_jwt, "player_id": str(discord_id)})


# ═════════════════════════════════════════════════════════════════════════════
#  GAME ACCOUNTS (username + password) — Discord not required
#
#  A game account resolves to a players row exactly like a Discord login does,
#  so everything downstream (all 126 authenticated handlers) is untouched: they
#  read players.id out of the session, and they cannot tell the difference.
#
#  The id is negative — see services/auth/identities.allocate_native_id.
# ═════════════════════════════════════════════════════════════════════════════


def _auth_bad(msg: str, code: str = "invalid_request", status: int = 400) -> web.Response:
    return web.json_response({"ok": False, "error": code, "message": msg}, status=status)


async def _json_body(request: web.Request) -> dict:
    try:
        b = await request.json()
        return b if isinstance(b, dict) else {}
    except Exception:
        return {}


async def handle_auth_native_signup(request: web.Request) -> web.Response:
    """POST /api/auth/native/signup — create a game account.

    Body: {username, email, password}
    Returns: {access_token, player_id}
    """
    bot = request.app["bot"]
    db = getattr(bot, "db", None)
    if db is None or db.pool is None:
        return _auth_bad("Database unavailable.", "database_unavailable", 503)

    from services.auth.identities import (
        PROVIDER_NATIVE,
        allocate_native_id,
        link_identity,
    )
    from services.auth.passwords import (
        hash_password,
        new_email_token,
        validate_email,
        validate_password,
        validate_username,
    )
    from services.auth.session_tokens import issue_session

    body = await _json_body(request)
    username = str(body.get("username") or "").strip()
    email = str(body.get("email") or "").strip()
    password = str(body.get("password") or "")

    ok, msg = validate_username(username)
    if not ok:
        return _auth_bad(msg)
    ok, msg = validate_email(email)
    if not ok:
        return _auth_bad(msg)
    ok, msg = validate_password(password)
    if not ok:
        return _auth_bad(msg)

    username_lc = username.lower()
    email_lc = email.lower()

    # Hash before the transaction: scrypt costs ~25ms and holding a DB
    # connection through it would let signups exhaust the pool.
    pw_hash = hash_password(password)

    try:
        async with db.transaction() as conn:
            taken = await conn.fetchval(
                "SELECT 1 FROM player_credentials WHERE username_lc=$1", username_lc
            )
            if taken:
                return _auth_bad("That username is taken.", "username_taken", 409)
            taken = await conn.fetchval(
                "SELECT 1 FROM player_credentials WHERE email_lc=$1", email_lc
            )
            if taken:
                # Deliberately explicit. Hiding this only moves the disclosure to
                # the signup attempt itself, and a player who forgot they had an
                # account deserves to be told.
                return _auth_bad(
                    "That email already has an account. Try signing in instead.",
                    "email_taken",
                    409,
                )

            player_id = -int(await conn.fetchval("SELECT nextval('native_player_id_seq')"))
            await conn.execute(
                "INSERT INTO players(id, username) VALUES($1, $2)", player_id, username
            )
            await conn.execute(
                """
                INSERT INTO player_credentials
                    (player_id, username, username_lc, email, email_lc, password_hash)
                VALUES ($1, $2, $3, $4, $5, $6)
                """,
                player_id,
                username,
                username_lc,
                email,
                email_lc,
                pw_hash,
            )
            await conn.execute(
                """
                INSERT INTO auth_identities (provider, provider_uid, player_id)
                VALUES ($1, $2, $3) ON CONFLICT (provider, provider_uid) DO NOTHING
                """,
                PROVIDER_NATIVE,
                username_lc,
                player_id,
            )
    except Exception as e:
        log.exception("native signup failed")
        return _auth_bad("Could not create the account.", "signup_failed", 500)

    # Verification mail is best-effort: a mail outage must not cost someone the
    # account they just made. They can play now and verify later.
    try:
        token, token_hash = new_email_token()
        await db.execute(
            """
            INSERT INTO auth_email_tokens (token_hash, player_id, kind, expires_at)
            VALUES ($1, $2, 'verify', NOW() + INTERVAL '7 days')
            """,
            token_hash,
            player_id,
        )
        from services.auth.email_sender import send_email_verify

        await send_email_verify(email, username, token)
    except Exception as e:
        log.warning("verify email not sent for %s: %s", player_id, e)

    session_jwt = issue_session(player_id, "native", identity={"username": username})
    return web.json_response({"access_token": session_jwt, "player_id": str(player_id)})


async def handle_auth_native_login(request: web.Request) -> web.Response:
    """POST /api/auth/native/login — body: {login, password}. `login` is a
    username or an email; players do not remember which they used."""
    bot = request.app["bot"]
    db = getattr(bot, "db", None)
    if db is None or db.pool is None:
        return _auth_bad("Database unavailable.", "database_unavailable", 503)

    from services.auth.identities import credentials_by_login
    from services.auth.passwords import hash_password, needs_rehash, verify_password
    from services.auth.session_tokens import issue_session

    body = await _json_body(request)
    login = str(body.get("login") or body.get("username") or "").strip()
    password = str(body.get("password") or "")
    if not login or not password:
        return _auth_bad("Enter your username and password.")

    # Second bucket, per-account: the IP bucket in the middleware does not stop
    # a botnet grinding one account.
    retry = _auth_login_throttle(login)
    if retry is not None:
        return _rate_limited_response(request, retry)

    row = await credentials_by_login(db, login)
    # Same message and roughly the same work whether the account exists or the
    # password is wrong — otherwise this endpoint enumerates usernames.
    if not row or not verify_password(password, row.get("password_hash") or ""):
        return _auth_bad("Wrong username or password.", "invalid_credentials", 401)

    player_id = int(row["player_id"])

    if needs_rehash(row.get("password_hash") or ""):
        try:
            await db.execute(
                "UPDATE player_credentials SET password_hash=$2, updated_at=NOW() WHERE player_id=$1",
                player_id,
                hash_password(password),
            )
        except Exception as e:
            log.warning("rehash failed for %s: %s", player_id, e)

    session_jwt = issue_session(player_id, "native", identity={"username": row.get("username")})
    return web.json_response({"access_token": session_jwt, "player_id": str(player_id)})


async def handle_auth_password_forgot(request: web.Request) -> web.Response:
    """POST /api/auth/password/forgot — body: {email}.

    Always reports success. Telling an anonymous caller whether an address has an
    account is an account-enumeration oracle, and the honest-looking version of
    this endpoint is the insecure one.
    """
    bot = request.app["bot"]
    db = getattr(bot, "db", None)
    generic = web.json_response(
        {"ok": True, "message": "If that email has an account, a reset link is on its way."}
    )
    if db is None or db.pool is None:
        return _auth_bad("Database unavailable.", "database_unavailable", 503)

    body = await _json_body(request)
    email = str(body.get("email") or "").strip().lower()
    if not email:
        return _auth_bad("Enter your email address.")

    retry = _auth_login_throttle(email)
    if retry is not None:
        return _rate_limited_response(request, retry)

    try:
        row = await db.fetchrow(
            "SELECT player_id, username, email FROM player_credentials WHERE email_lc=$1", email
        )
        if row:
            from services.auth.email_sender import send_password_reset
            from services.auth.passwords import new_email_token

            token, token_hash = new_email_token()
            await db.execute(
                """
                INSERT INTO auth_email_tokens (token_hash, player_id, kind, expires_at)
                VALUES ($1, $2, 'reset', NOW() + INTERVAL '1 hour')
                """,
                token_hash,
                int(row["player_id"]),
            )
            await send_password_reset(row["email"], row["username"], token)
    except Exception as e:
        log.exception("password forgot failed: %s", e)

    return generic


async def handle_auth_password_reset(request: web.Request) -> web.Response:
    """POST /api/auth/password/reset — body: {token, password}."""
    bot = request.app["bot"]
    db = getattr(bot, "db", None)
    if db is None or db.pool is None:
        return _auth_bad("Database unavailable.", "database_unavailable", 503)

    from services.auth.passwords import hash_password, hash_email_token, validate_password
    from services.auth.session_tokens import issue_session

    body = await _json_body(request)
    token = str(body.get("token") or "").strip()
    password = str(body.get("password") or "")
    if not token:
        return _auth_bad("That reset link is incomplete.", "invalid_token", 400)
    ok, msg = validate_password(password)
    if not ok:
        return _auth_bad(msg)

    th = hash_email_token(token)
    pw_hash = hash_password(password)

    try:
        async with db.transaction() as conn:
            row = await conn.fetchrow(
                """
                SELECT id, player_id FROM auth_email_tokens
                WHERE token_hash=$1 AND kind='reset' AND used_at IS NULL AND expires_at > NOW()
                FOR UPDATE
                """,
                th,
            )
            if not row:
                return _auth_bad(
                    "That reset link has expired or was already used.", "invalid_token", 400
                )
            player_id = int(row["player_id"])
            await conn.execute(
                "UPDATE player_credentials SET password_hash=$2, updated_at=NOW() WHERE player_id=$1",
                player_id,
                pw_hash,
            )
            # Mark used inside the same transaction: a token that reset a
            # password but stayed valid would be a replay.
            await conn.execute("UPDATE auth_email_tokens SET used_at=NOW() WHERE id=$1", row["id"])
            # Using a reset link proves control of the mailbox.
            await conn.execute(
                "UPDATE player_credentials SET email_verified=TRUE WHERE player_id=$1", player_id
            )
            cred = await conn.fetchrow(
                "SELECT username FROM player_credentials WHERE player_id=$1", player_id
            )
    except Exception:
        log.exception("password reset failed")
        return _auth_bad("Could not reset the password.", "reset_failed", 500)

    session_jwt = issue_session(
        player_id, "native", identity={"username": cred["username"] if cred else None}
    )
    return web.json_response({"ok": True, "access_token": session_jwt, "player_id": str(player_id)})


async def handle_auth_email_verify(request: web.Request) -> web.Response:
    """POST /api/auth/email/verify — body: {token}."""
    bot = request.app["bot"]
    db = getattr(bot, "db", None)
    if db is None or db.pool is None:
        return _auth_bad("Database unavailable.", "database_unavailable", 503)

    from services.auth.passwords import hash_email_token

    body = await _json_body(request)
    token = str(body.get("token") or "").strip()
    if not token:
        return _auth_bad("That link is incomplete.", "invalid_token", 400)

    try:
        async with db.transaction() as conn:
            row = await conn.fetchrow(
                """
                SELECT id, player_id FROM auth_email_tokens
                WHERE token_hash=$1 AND kind='verify' AND used_at IS NULL AND expires_at > NOW()
                FOR UPDATE
                """,
                hash_email_token(token),
            )
            if not row:
                return _auth_bad("That link has expired or was already used.", "invalid_token", 400)
            await conn.execute(
                "UPDATE player_credentials SET email_verified=TRUE, updated_at=NOW() WHERE player_id=$1",
                int(row["player_id"]),
            )
            await conn.execute("UPDATE auth_email_tokens SET used_at=NOW() WHERE id=$1", row["id"])
    except Exception:
        log.exception("email verify failed")
        return _auth_bad("Could not verify that email.", "verify_failed", 500)

    return web.json_response({"ok": True})


async def _character_summary(db, player_id: int) -> Optional[dict]:
    """Enough for a player to recognise a character they might be about to lose."""
    row = await db.fetchrow(
        """
        SELECT name, level, class, specialization, gold, created_at
        FROM characters WHERE player_id=$1 AND is_active=TRUE
        ORDER BY created_at DESC LIMIT 1
        """,
        int(player_id),
    )
    if not row:
        return None
    d = dict(row)
    return {
        "name": d.get("name"),
        "level": d.get("level"),
        "class": d.get("class"),
        "specialization": d.get("specialization"),
        "gold": int(d.get("gold") or 0),
        "created_at": str(d.get("created_at") or ""),
    }


async def handle_auth_link_status(request: web.Request) -> web.Response:
    """GET /api/auth/link/status — what is attached to this account."""
    user, player_id, _char, db = await _authed_discord_user_and_char(request)
    from services.auth.identities import credentials_for_player, identities_for_player

    idents = await identities_for_player(db, player_id)
    cred = await credentials_for_player(db, player_id)
    return web.json_response(
        {
            "ok": True,
            "player_id": str(player_id),
            "providers": [i["provider"] for i in idents],
            "has_password": bool(cred),
            "username": (cred or {}).get("username"),
            "email_verified": bool((cred or {}).get("email_verified")),
        }
    )


async def handle_auth_link_discord(request: web.Request) -> web.Response:
    """POST /api/auth/link/discord — body: {code, redirect_uri?}

    Attaches a Discord account to the *currently signed-in* player.

    If that Discord account already has its own character, nothing is
    overwritten: we return both characters plus a short-lived pick_token, and
    the player decides. See handle_auth_link_resolve.
    """
    user, player_id, _char, db = await _authed_discord_user_and_char(request)

    secret = (os.getenv("DISCORD_CLIENT_SECRET") or "").strip()
    client_id = _client_id_for_app(request.app["bot"])
    if not secret or not client_id:
        return _auth_bad("Discord linking isn't configured.", "server_misconfigured", 503)

    body = await _json_body(request)
    code = body.get("code")
    if not code or not isinstance(code, str):
        return _auth_bad("Missing the Discord authorization code.", "missing_code")
    redirect_hint = body.get("redirect_uri")
    redirect_hint = redirect_hint.strip() if isinstance(redirect_hint, str) and redirect_hint.strip() else None

    token_payload = await _exchange_oauth_code(code, client_id, secret, redirect_hint)
    discord_token = token_payload.get("access_token")
    if not discord_token:
        return _auth_bad("Discord didn't return a token.", "no_access_token")
    du = await _discord_user_from_token(discord_token)
    if not du:
        return _auth_bad("Could not read that Discord account.", "invalid_token", 401)

    discord_uid = str(int(du["id"]))

    from services.auth.identities import IdentityConflict, PROVIDER_DISCORD, link_identity
    from services.auth.session_tokens import issue_link_intent

    try:
        await link_identity(db, PROVIDER_DISCORD, discord_uid, player_id)
    except IdentityConflict as e:
        # The interesting case. Show them both, let them choose.
        return web.json_response(
            {
                "ok": False,
                "error": "identity_conflict",
                "conflict": True,
                "pick_token": issue_link_intent(player_id, PROVIDER_DISCORD, discord_uid),
                "current": await _character_summary(db, player_id),
                "other": await _character_summary(db, e.existing_player_id),
                "message": "That Discord account already has a character. Choose which one to keep.",
            },
            status=409,
        )

    return web.json_response({"ok": True, "linked": True, "provider": "discord"})


async def handle_auth_link_resolve(request: web.Request) -> web.Response:
    """POST /api/auth/link/resolve — body: {pick_token, keep: "current"|"other"}

    Answers "which character do I keep?" by re-pointing the identity. Nothing is
    deleted: the player row that loses the identity keeps its character,
    inventory and gold, and re-pointing back restores it exactly.
    """
    user, player_id, _char, db = await _authed_discord_user_and_char(request)

    from services.auth.identities import repoint_identity, resolve_identity
    from services.auth.session_tokens import verify_link_intent

    body = await _json_body(request)
    claims = verify_link_intent(str(body.get("pick_token") or ""))
    keep = str(body.get("keep") or "")
    if not claims:
        return _auth_bad("That choice expired. Start the link again.", "invalid_token", 400)
    if keep not in ("current", "other"):
        return _auth_bad("Choose which character to keep.", "invalid_request")
    # The token proves who asked. Re-check against the live session so a token
    # cannot be replayed by a different account.
    if int(claims["pid"]) != int(player_id):
        return _auth_bad("That choice belongs to a different account.", "forbidden", 403)

    provider, uid = str(claims["prov"]), str(claims["uid"])

    if keep == "current":
        # Discord now signs in to THIS account. The other player row keeps its
        # character; it just isn't reachable by that Discord login any more.
        await repoint_identity(db, provider, uid, player_id)
        return web.json_response(
            {"ok": True, "kept": "current", "provider": provider}
        )

    # keep == "other": abandon this account's character in favour of the Discord
    # one. The game account's username/password must follow, or they'd sign in
    # to an account they just chose to leave.
    other_player_id = await resolve_identity(db, provider, uid)
    if other_player_id is None:
        return _auth_bad("That Discord account is no longer linked.", "invalid_state", 409)
    try:
        async with db.transaction() as conn:
            await conn.execute(
                "UPDATE player_credentials SET player_id=$2, updated_at=NOW() WHERE player_id=$1",
                int(player_id),
                int(other_player_id),
            )
            await conn.execute(
                "UPDATE auth_identities SET player_id=$2 WHERE player_id=$1 AND provider='native'",
                int(player_id),
                int(other_player_id),
            )
    except Exception:
        log.exception("link resolve (keep=other) failed")
        return _auth_bad("Could not move your login over.", "resolve_failed", 500)

    from services.auth.session_tokens import issue_session

    # They are a different player now — issue a session for the account they kept.
    new_token = issue_session(int(other_player_id), "native", identity={"username": user.get("username")})
    return web.json_response(
        {"ok": True, "kept": "other", "access_token": new_token, "player_id": str(other_player_id)}
    )


async def _equipped_set_summary(db, items: list) -> list:
    """What sets the character is wearing, and what the next tier would give.

    `max_pieces` comes from the templates table rather than a constant, so a
    designer adding a fifth piece to a set changes the player-facing "3 / 4"
    without touching code — and so we never advertise a tier that no amount of
    farming could reach.
    """
    from services.character.item_sets import summarize_sets

    equipped_set_ids = [
        it.get("set_id") for it in items if it.get("is_equipped") and it.get("set_id")
    ]
    if not equipped_set_ids:
        return []
    try:
        rows = await db.fetch(
            "SELECT set_id, count(*) AS n FROM item_templates WHERE set_id = ANY($1::text[]) GROUP BY set_id",
            list({str(s) for s in equipped_set_ids}),
        )
        sizes = {r["set_id"]: int(r["n"]) for r in rows}
    except Exception as e:
        # Losing the sizes only costs us the "x / y" denominator; the active
        # bonus is still correct, so degrade rather than fail the whole payload.
        log.warning("set size lookup failed: %s", e)
        sizes = {}
    return summarize_sets(equipped_set_ids, sizes)


async def handle_inventory(request: web.Request) -> web.Response:
    bot = request.app["bot"]
    db = getattr(bot, "db", None)
    if db is None or db.pool is None:
        raise web.HTTPServiceUnavailable(text=json.dumps({"error": "database_unavailable"}), content_type="application/json")

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise web.HTTPUnauthorized(text=json.dumps({"error": "missing_bearer"}), content_type="application/json")
    token = auth_header[7:].strip()

    user = await _user_from_bearer(token)
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
    craft_svc = CraftingService(db)
    craft_job = await craft_svc.get_inflight_job(char["id"])
    craft_recipes = await craft_svc.list_recipes()
    forge_rarity_rules = await craft_svc.list_rarity_rules()
    # Inventory capacity metadata (bag only: unequipped rows).
    player = await db.fetchrow(
        """SELECT p.is_premium FROM players p
           JOIN characters c ON c.player_id=p.id WHERE c.id=$1""",
        char["id"],
    )
    bag_slots_max = (
        Settings.PREMIUM_INVENTORY_SLOTS
        if (player and player.get("is_premium"))
        else Settings.FREE_INVENTORY_SLOTS
    )
    bag_slots_used = sum(1 for it in (items or []) if not bool((it or {}).get("is_equipped")))
    char_dict = dict(char)
    sk = char_dict.get("specialization")
    if sk:
        spec = SPECIALIZATIONS.get(sk)
        if spec:
            char_dict["specialization_name"] = spec.name
    lvl = int(char_dict.get("level") or 1)
    total_xp = int(char_dict.get("xp") or 0)
    floor_xp = CharacterService.total_xp_to_reach(lvl)
    char_dict["xp_in_level"] = max(0, total_xp - floor_xp)
    char_dict["xp_to_next"] = (
        0 if lvl >= Settings.MAX_LEVEL else CharacterService.xp_for_next_level(lvl)
    )
    if char_dict.get("guild_id"):
        g_row = await db.fetchrow(
            "SELECT name, tag FROM guilds WHERE id=$1",
            char_dict["guild_id"],
        )
        if g_row:
            char_dict["guild_name"] = g_row["name"]
            char_dict["guild_tag"] = g_row["tag"]
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
                "bag_slots_used": bag_slots_used,
                "bag_slots_max": int(bag_slots_max),
                "items": items,
                # Set bonuses have been applied to stats since forever
                # (CharacterService.get_derived_stats) but were never exposed, so
                # the client could not show what a player was already receiving —
                # or what they were two pieces away from. Same table that grants
                # them, so the display cannot drift from the maths.
                "item_sets": await _equipped_set_summary(db, items),
                "craft_job": _json_safe(craft_job),
                "craft_recipes": _json_safe(craft_recipes),
                "forge_rarity_rules": _json_safe(forge_rarity_rules),
                "forge_output_max_level_req": 35,
            }
        )
    )


async def handle_item_salvage(request: web.Request) -> web.Response:
    bot = request.app["bot"]
    db = getattr(bot, "db", None)
    if db is None or db.pool is None:
        raise web.HTTPServiceUnavailable(text=json.dumps({"error": "database_unavailable"}), content_type="application/json")

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise web.HTTPUnauthorized(text=json.dumps({"error": "missing_bearer"}), content_type="application/json")
    token = auth_header[7:].strip()
    user = await _user_from_bearer(token)
    if not user:
        raise web.HTTPUnauthorized(text=json.dumps({"error": "invalid_token"}), content_type="application/json")

    try:
        body = await request.json()
    except json.JSONDecodeError:
        body = {}
    if not isinstance(body, dict):
        body = {}

    raw_ids = body.get("item_ids")
    if isinstance(raw_ids, list) and raw_ids:
        id_list = [str(x).strip() for x in raw_ids if str(x).strip()][:40]
    else:
        one = (body.get("item_id") or "").strip()
        id_list = [one] if one else []

    if not id_list:
        raise web.HTTPBadRequest(text=json.dumps({"error": "missing_item_id"}), content_type="application/json")

    discord_id = int(user["id"])
    char_svc = CharacterService(db)
    inv_svc = InventoryService(db)
    craft_svc = CraftingService(db)
    char = await char_svc.get_character(discord_id)
    if not char:
        return web.json_response({"ok": False, "error": "no_character", "message": "No character found."}, status=400)

    results = []
    ok_any = False
    for sid in id_list:
        try:
            uid = UUID(sid)
        except ValueError:
            results.append({"item_id": sid, "ok": False, "message": "Invalid item id."})
            continue
        ok, msg, pay = await inv_svc.salvage(char["id"], uid)
        if ok and pay:
            ok_any = True
            g = int(pay.get("gold") or 0)
            if g > 0:
                await char_svc.add_gold(char["id"], g, "salvage")
            xp = int(pay.get("crafting_xp") or 0)
            if xp > 0:
                await craft_svc.add_crafting_xp(char["id"], xp)
        results.append({"item_id": sid, "ok": ok, "message": msg, "payload": _json_safe(pay) if pay else None})

    summary = next((r.get("message") for r in reversed(results) if r.get("ok")), None)
    return web.json_response({"ok": ok_any, "message": summary or ("Salvaged." if ok_any else "Nothing salvaged."), "results": results})


async def handle_craft_start(request: web.Request) -> web.Response:
    bot = request.app["bot"]
    db = getattr(bot, "db", None)
    if db is None or db.pool is None:
        raise web.HTTPServiceUnavailable(text=json.dumps({"error": "database_unavailable"}), content_type="application/json")

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise web.HTTPUnauthorized(text=json.dumps({"error": "missing_bearer"}), content_type="application/json")
    token = auth_header[7:].strip()
    user = await _user_from_bearer(token)
    if not user:
        raise web.HTTPUnauthorized(text=json.dumps({"error": "invalid_token"}), content_type="application/json")

    try:
        body = await request.json()
    except json.JSONDecodeError:
        body = {}
    if not isinstance(body, dict):
        body = {}

    recipe_id = (body.get("recipe_id") or "").strip()
    src = (body.get("source_item_id") or "").strip()
    if not recipe_id or not src:
        raise web.HTTPBadRequest(text=json.dumps({"error": "missing_fields"}), content_type="application/json")

    try:
        src_uid = UUID(src)
    except ValueError:
        return web.json_response({"ok": False, "message": "Invalid source item id."}, status=400)

    discord_id = int(user["id"])
    char_svc = CharacterService(db)
    inv_svc = InventoryService(db)
    craft_svc = CraftingService(db)
    char = await char_svc.get_character(discord_id)
    if not char:
        return web.json_response({"ok": False, "error": "no_character", "message": "No character found."}, status=400)

    ok, msg, job = await craft_svc.start_craft(char["id"], recipe_id, src_uid, inv_svc, char_svc)
    status = 200 if ok else 400
    return web.json_response({"ok": ok, "message": msg, "craft_job": _json_safe(job)}, status=status)


async def handle_craft_claim(request: web.Request) -> web.Response:
    bot = request.app["bot"]
    db = getattr(bot, "db", None)
    if db is None or db.pool is None:
        raise web.HTTPServiceUnavailable(text=json.dumps({"error": "database_unavailable"}), content_type="application/json")

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise web.HTTPUnauthorized(text=json.dumps({"error": "missing_bearer"}), content_type="application/json")
    token = auth_header[7:].strip()
    user = await _user_from_bearer(token)
    if not user:
        raise web.HTTPUnauthorized(text=json.dumps({"error": "invalid_token"}), content_type="application/json")

    discord_id = int(user["id"])
    char_svc = CharacterService(db)
    inv_svc = InventoryService(db)
    craft_svc = CraftingService(db)
    char = await char_svc.get_character(discord_id)
    if not char:
        return web.json_response({"ok": False, "error": "no_character", "message": "No character found."}, status=400)

    ok, msg, data = await craft_svc.claim_craft(char["id"], inv_svc)
    status = 200 if ok else 400
    return web.json_response({"ok": ok, "message": msg, "result": _json_safe(data)}, status=status)


async def handle_forge_options(request: web.Request) -> web.Response:
    bot = request.app["bot"]
    db = getattr(bot, "db", None)
    if db is None or db.pool is None:
        raise web.HTTPServiceUnavailable(text=json.dumps({"error": "database_unavailable"}), content_type="application/json")

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise web.HTTPUnauthorized(text=json.dumps({"error": "missing_bearer"}), content_type="application/json")
    token = auth_header[7:].strip()
    user = await _user_from_bearer(token)
    if not user:
        raise web.HTTPUnauthorized(text=json.dumps({"error": "invalid_token"}), content_type="application/json")

    raw_id = (request.rel_url.query.get("item_id") or "").strip()
    if not raw_id:
        raise web.HTTPBadRequest(text=json.dumps({"error": "missing_item_id"}), content_type="application/json")
    try:
        item_uid = UUID(raw_id)
    except ValueError:
        return web.json_response({"ok": False, "message": "Invalid item id."}, status=400)

    discord_id = int(user["id"])
    char_svc = CharacterService(db)
    craft_svc = CraftingService(db)
    char = await char_svc.get_character(discord_id)
    if not char:
        return web.json_response({"ok": False, "error": "no_character", "message": "No character found."}, status=400)

    ok, msg, data = await craft_svc.forge_options(char["id"], item_uid)
    status = 200 if ok else 400
    return web.json_response({"ok": ok, "message": msg, "options": _json_safe(data)}, status=status)


async def handle_forge_start(request: web.Request) -> web.Response:
    bot = request.app["bot"]
    db = getattr(bot, "db", None)
    if db is None or db.pool is None:
        raise web.HTTPServiceUnavailable(text=json.dumps({"error": "database_unavailable"}), content_type="application/json")

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise web.HTTPUnauthorized(text=json.dumps({"error": "missing_bearer"}), content_type="application/json")
    token = auth_header[7:].strip()
    user = await _user_from_bearer(token)
    if not user:
        raise web.HTTPUnauthorized(text=json.dumps({"error": "invalid_token"}), content_type="application/json")

    try:
        body = await request.json()
    except json.JSONDecodeError:
        body = {}
    if not isinstance(body, dict):
        body = {}

    path = (body.get("path") or "").strip().lower()
    item_raw = (body.get("item_id") or "").strip()
    recipe_id = (body.get("recipe_id") or "").strip() or None
    if path not in ("a", "b") or not item_raw:
        raise web.HTTPBadRequest(text=json.dumps({"error": "missing_fields"}), content_type="application/json")
    try:
        item_uid = UUID(item_raw)
    except ValueError:
        return web.json_response({"ok": False, "message": "Invalid item id."}, status=400)

    discord_id = int(user["id"])
    char_svc = CharacterService(db)
    inv_svc = InventoryService(db)
    craft_svc = CraftingService(db)
    char = await char_svc.get_character(discord_id)
    if not char:
        return web.json_response({"ok": False, "error": "no_character", "message": "No character found."}, status=400)

    ok, msg, job = await craft_svc.start_forge(char["id"], path, item_uid, recipe_id, inv_svc, char_svc)
    status = 200 if ok else 400
    return web.json_response({"ok": ok, "message": msg, "craft_job": _json_safe(job)}, status=status)


async def handle_forge_claim(request: web.Request) -> web.Response:
    """Same as POST /api/game/craft/claim — unified forge job claim."""
    bot = request.app["bot"]
    db = getattr(bot, "db", None)
    if db is None or db.pool is None:
        raise web.HTTPServiceUnavailable(text=json.dumps({"error": "database_unavailable"}), content_type="application/json")

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise web.HTTPUnauthorized(text=json.dumps({"error": "missing_bearer"}), content_type="application/json")
    token = auth_header[7:].strip()
    user = await _user_from_bearer(token)
    if not user:
        raise web.HTTPUnauthorized(text=json.dumps({"error": "invalid_token"}), content_type="application/json")

    discord_id = int(user["id"])
    char_svc = CharacterService(db)
    inv_svc = InventoryService(db)
    craft_svc = CraftingService(db)
    char = await char_svc.get_character(discord_id)
    if not char:
        return web.json_response({"ok": False, "error": "no_character", "message": "No character found."}, status=400)

    ok, msg, data = await craft_svc.claim_craft(char["id"], inv_svc)
    status = 200 if ok else 400
    return web.json_response({"ok": ok, "message": msg, "result": _json_safe(data)}, status=status)


async def handle_battle_pass_get(request: web.Request) -> web.Response:
    try:
        _user, _discord_id, char, db = await _authed_discord_user_and_char(request)
    except web.HTTPException:
        raise
    if not char:
        return web.json_response(_json_safe({"ok": False, "error": "no_character"}), status=400)
    from services.battle_pass.battle_pass_service import BattlePassService

    bp = BattlePassService(db)
    state = await bp.get_state(_uuid_from_any(char["id"]))
    return web.json_response(_json_safe(state))


async def handle_battle_pass_claim(request: web.Request) -> web.Response:
    try:
        _user, _discord_id, char, db = await _authed_discord_user_and_char(request)
    except web.HTTPException:
        raise
    if not char:
        return web.json_response(_json_safe({"ok": False, "error": "no_character"}), status=400)
    try:
        body = await request.json()
    except (json.JSONDecodeError, ValueError, TypeError):
        body = {}
    if not isinstance(body, dict):
        body = {}
    tier = int(body.get("tier") or 0)
    track = str(body.get("track") or "free")
    from services.battle_pass.battle_pass_service import BattlePassService

    bp = BattlePassService(db)
    ok, msg, delivery = await bp.claim_tier(_uuid_from_any(char["id"]), tier, track)
    status = 200 if ok else 400
    return web.json_response(_json_safe({"ok": ok, "message": msg, "delivery": delivery}), status=status)


async def handle_daily_login_claim(request: web.Request) -> web.Response:
    try:
        _user, _discord_id, char, db = await _authed_discord_user_and_char(request)
    except web.HTTPException:
        raise
    if not char:
        return web.json_response(_json_safe({"ok": False, "error": "no_character"}), status=400)
    from services.daily.daily_login_service import DailyLoginService
    from services.battle_pass.battle_pass_service import BattlePassService

    char_svc = CharacterService(db)
    char_id = _uuid_from_any(char["id"])
    login_svc = DailyLoginService(db)
    result = await login_svc.claim_daily_reward(char_id)
    if not result.get("claimed"):
        return web.json_response(_json_safe({"ok": False, "message": result.get("message"), **result}))

    await login_svc.apply_economy_rewards(char_svc, char_id, result)
    bp = BattlePassService(db)
    pass_xp = await bp.on_daily_login_claimed(char_id, int(result.get("current_streak") or 0))
    state = await bp.get_state(char_id)
    return web.json_response(
        _json_safe(
            {
                "ok": True,
                "login": result,
                "pass_xp_grants": pass_xp,
                "battle_pass": state,
            }
        )
    )


async def handle_battle_pass_playtime(request: web.Request) -> web.Response:
    """POST JSON { minutes } — grant capped playtime pass XP for Activity session."""
    try:
        _user, _discord_id, char, db = await _authed_discord_user_and_char(request)
    except web.HTTPException:
        raise
    if not char:
        return web.json_response(_json_safe({"ok": False, "error": "no_character"}), status=400)
    try:
        body = await request.json()
    except (json.JSONDecodeError, ValueError, TypeError):
        body = {}
    if not isinstance(body, dict):
        body = {}
    minutes = max(0, min(60, int(body.get("minutes") or 0)))
    from services.battle_pass.battle_pass_service import BattlePassService

    bp = BattlePassService(db)
    grant = await bp.grant_playtime_xp(_uuid_from_any(char["id"]), minutes)
    return web.json_response(_json_safe({"ok": True, "grant": grant}))


async def handle_talents_get(request: web.Request) -> web.Response:
    try:
        _user, _discord_id, char, db = await _authed_discord_user_and_char(request)
    except web.HTTPException:
        raise
    if not char:
        return web.json_response(_json_safe({"ok": False, "error": "no_character"}), status=400)
    from services.talents.talent_service import TalentService

    char_svc = CharacterService(db)
    fresh = await char_svc.get_by_id(_uuid_from_any(char["id"]))
    state = await TalentService(db).get_tree_state(dict(fresh) if fresh else char)
    mastery = await char_svc.get_class_mastery(_uuid_from_any(char["id"]), char.get("class") or "")
    state["class_mastery"] = mastery
    return web.json_response(_json_safe(state))


async def handle_talents_allocate(request: web.Request) -> web.Response:
    try:
        _user, _discord_id, char, db = await _authed_discord_user_and_char(request)
    except web.HTTPException:
        raise
    if not char:
        return web.json_response(_json_safe({"ok": False, "error": "no_character"}), status=400)
    try:
        body = await request.json()
    except (json.JSONDecodeError, ValueError, TypeError):
        body = {}
    if not isinstance(body, dict):
        body = {}
    node_id = str(body.get("node_id") or "").strip()
    delta = int(body.get("delta") or body.get("ranks") or 1)
    from services.talents.talent_service import TalentService

    char_svc = CharacterService(db)
    fresh = await char_svc.get_by_id(_uuid_from_any(char["id"]))
    ok, msg, state = await TalentService(db).allocate(dict(fresh) if fresh else char, node_id, delta)
    status = 200 if ok else 400
    return web.json_response(_json_safe({"ok": ok, "message": msg, **(state or {})}), status=status)


async def handle_talents_respec(request: web.Request) -> web.Response:
    try:
        _user, _discord_id, char, db = await _authed_discord_user_and_char(request)
    except web.HTTPException:
        raise
    if not char:
        return web.json_response(_json_safe({"ok": False, "error": "no_character"}), status=400)
    from services.talents.talent_service import TalentService

    char_svc = CharacterService(db)
    fresh = await char_svc.get_by_id(_uuid_from_any(char["id"]))
    ok, msg, state = await TalentService(db).respec(dict(fresh) if fresh else char, char_svc)
    status = 200 if ok else 400
    return web.json_response(_json_safe({"ok": ok, "message": msg, **(state or {})}), status=status)


async def handle_character_stats(request: web.Request) -> web.Response:
    """GET /api/game/character/stats — Derived combat stats (includes equipped item rolls)."""
    bot = request.app["bot"]
    db = getattr(bot, "db", None)
    if db is None or db.pool is None:
        raise web.HTTPServiceUnavailable(text=json.dumps({"error": "database_unavailable"}), content_type="application/json")

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise web.HTTPUnauthorized(text=json.dumps({"error": "missing_bearer"}), content_type="application/json")
    token = auth_header[7:].strip()

    user = await _user_from_bearer(token)
    if not user:
        raise web.HTTPUnauthorized(text=json.dumps({"error": "invalid_token"}), content_type="application/json")

    discord_id = int(user["id"])
    char_svc = CharacterService(db)
    char = await char_svc.get_character(discord_id)
    if not char:
        return web.json_response({"ok": False, "error": "no_character", "message": "Create a character first."}, status=400)

    stats = await char_svc.total_stats(char["id"])
    mastery = await char_svc.get_class_mastery(char["id"], char.get("class") or "")
    top_abilities = await char_svc.top_ability_masteries(char["id"], limit=6)
    payload = {
        "ok": True,
        "attack_power": stats.get("attack_power", 0),
        "spell_power": stats.get("spell_power", 0),
        "dmg_min": stats.get("dmg_min", 0),
        "dmg_max": stats.get("dmg_max", 0),
        "armor": stats.get("armor", 0),
        "crit_chance": stats.get("crit_chance", 0.0),
        "dodge_chance": stats.get("dodge_chance", 0.0),
        "haste": stats.get("haste", 0.0),
        "lifesteal": stats.get("lifesteal", 0.0),
        "resistance": stats.get("resistance", 0),
        "hit_rating": stats.get("hit_rating", 0.0),
        "class_mastery": mastery,
        "top_ability_mastery": top_abilities,
    }
    return web.json_response(_json_safe(payload))


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

    user = await _user_from_bearer(token)
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
    q = request.rel_url.query.get("guild_id") or request.rel_url.query.get("guildId")
    if q and str(q).strip().isdigit():
        return int(str(q).strip())
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

    user = await _user_from_bearer(token)
    if not user:
        raise web.HTTPUnauthorized(text=json.dumps({"error": "invalid_token"}), content_type="application/json")

    discord_id = int(user["id"])
    char_svc = CharacterService(db)
    char = await char_svc.get_character(discord_id)
    if not char:
        return web.json_response(_json_safe({"enemies": [], "error": "no_character"}))

    zone_key = (request.query.get("zone_key") or "").strip()
    if zone_key:
        # Allow the client to request enemies for a specific zone (e.g. quest objectives),
        # without mutating the character's actual location.
        char = dict(char)
        char["current_zone"] = zone_key

    payload = await activity_combat_api.list_zone_enemies(char)
    return web.json_response(_json_safe(payload))


async def handle_game_dungeons(request: web.Request) -> web.Response:
    """Static dungeon catalog + per-floor enemy preview (aligned with ``config.settings.DUNGEONS``)."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise web.HTTPUnauthorized(text=json.dumps({"error": "missing_bearer"}), content_type="application/json")
    token = auth_header[7:].strip()

    user = await _user_from_bearer(token)
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

    user = await _user_from_bearer(token)
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
    return web.json_response(_json_safe({
        "ok": True,
        "run_id": str(run_id),
        "dungeon": {
            "key": dungeon_key,
            "name": dungeon_config.name,
            "emoji": dungeon_config.emoji,
        },
        "participants": run["participants"],
    }))


async def handle_dungeon_party_invite(request: web.Request) -> web.Response:
    """POST /api/game/dungeon/party/invite — Send invite to player (creates pending invite)."""
    bot = request.app["bot"]
    db = getattr(bot, "db", None)
    if db is None or db.pool is None:
        raise web.HTTPServiceUnavailable(text=json.dumps({"error": "database_unavailable"}), content_type="application/json")

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise web.HTTPUnauthorized(text=json.dumps({"error": "missing_bearer"}), content_type="application/json")
    token = auth_header[7:].strip()

    user = await _user_from_bearer(token)
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
    from services.social.social_service import SocialService

    char_svc = CharacterService(db)
    dungeon_svc = DungeonService(db)
    social_svc = SocialService(db)

    char = await char_svc.get_character(discord_id)
    if not char:
        return web.json_response({"error": "no_character", "message": "Create a character first."}, status=400)

    try:
        target_discord_id = int(target_user_id)
    except (TypeError, ValueError):
        return web.json_response({"error": "invalid_target", "message": "Invalid target user."}, status=400)

    if await social_svc.is_ignored(discord_id, target_discord_id):
        return web.json_response(
            {"ok": False, "error": "blocked", "message": "You cannot invite this player."},
            status=400,
        )

    if not await social_svc.is_friend(discord_id, target_discord_id):
        if not await social_svc.allows_party_invites_from_strangers(target_discord_id):
            return web.json_response(
                {
                    "ok": False,
                    "error": "party_invites_disabled",
                    "message": "That player is not accepting party invites from non-friends.",
                },
                status=400,
            )

    run = await dungeon_svc.get_active_run(char["id"])
    if not run:
        return web.json_response({"error": "not_in_dungeon", "message": "You're not in a dungeon party.", "status": 400})

    # Check if leader - convert both IDs to strings for proper UUID comparison
    is_leader = any(str(p["id"]) == str(char["id"]) and p.get("role") == "leader" for p in run["participants"])
    if not is_leader:
        return web.json_response({"error": "not_leader", "message": "Only the leader can invite."}, status=403)

    # Get target character
    target_char = await char_svc.get_character(int(target_user_id))
    if not target_char:
        return web.json_response({"error": "target_no_character", "message": "That user has no character."}, status=400)

    if target_char["in_dungeon"]:
        return web.json_response({"error": "target_in_dungeon", "message": "That player is already in a dungeon."}, status=400)

    # Check if already invited
    existing = await db.fetchrow(
        """
        SELECT id, status FROM dungeon_party_invites
        WHERE run_id = $1 AND invitee_id = $2 AND status = 'pending'
        """,
        run["id"],
        target_char["id"],
    )
    if existing:
        return web.json_response({
            "ok": True,
            "message": f"Invite already sent to {target_char['name']}.",
            "already_invited": True,
            "status": existing["status"],
        })

    # Create pending invite
    invite_id = await db.fetchval(
        """
        INSERT INTO dungeon_party_invites (run_id, inviter_id, invitee_id, status)
        VALUES ($1, $2, $3, 'pending')
        RETURNING id
        """,
        run["id"],
        char["id"],
        target_char["id"],
    )

    return web.json_response(_json_safe({
        "ok": True,
        "message": f"Invite sent to {target_char['name']}. They can accept in the Activity.",
        "invite_id": str(invite_id),
        "expires_in_minutes": 15,
    }))


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

    user = await _user_from_bearer(token)
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
    return web.json_response(_json_safe({
        "ok": True,
        "message": "Joined the party!",
        "run_id": str(run_id),
        "participants": run["participants"],
    }))


async def handle_dungeon_party_invites_list(request: web.Request) -> web.Response:
    """GET /api/game/dungeon/party/invites — Get pending invites for current player."""
    try:
        _user, discord_id, char, db = await _authed_discord_user_and_char(request)
    except web.HTTPException:
        raise
    if not char:
        return web.json_response(_json_safe({"ok": False, "error": "no_character", "invites": []}), status=400)

    # Get pending invites (not expired)
    rows = await db.fetch(
        """
        SELECT dpi.id, dpi.run_id, dpi.inviter_id, dpi.created_at, dpi.expires_at,
               dr.dungeon_key,
               c_inviter.name as inviter_name,
               c_inviter.level as inviter_level,
               c_inviter.class as inviter_class
        FROM dungeon_party_invites dpi
        JOIN dungeon_runs dr ON dpi.run_id = dr.id
        JOIN characters c_inviter ON dpi.inviter_id = c_inviter.id
        WHERE dpi.invitee_id = $1 AND dpi.status = 'pending' AND dpi.expires_at > NOW()
        ORDER BY dpi.created_at DESC
        LIMIT 10
        """,
        char["id"],
    )
    
    invites = [
        {
            "invite_id": str(r["id"]),
            "run_id": str(r["run_id"]),
            "dungeon_key": r["dungeon_key"],
            "inviter": {
                "id": str(r["inviter_id"]),
                "name": r["inviter_name"],
                "level": r["inviter_level"],
                "class": r["inviter_class"],
            },
            "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            "expires_at": r["expires_at"].isoformat() if r["expires_at"] else None,
        }
        for r in rows
    ]
    
    return web.json_response(_json_safe({"ok": True, "invites": invites}))


async def handle_dungeon_party_invite_accept(request: web.Request) -> web.Response:
    """POST /api/game/dungeon/party/invite/accept — Accept invite and join party."""
    try:
        _user, discord_id, char, db = await _authed_discord_user_and_char(request)
    except web.HTTPException:
        raise
    if not char:
        return web.json_response({"error": "no_character", "message": "Create a character first."}, status=400)

    try:
        body = await request.json()
    except json.JSONDecodeError:
        body = {}
    if not isinstance(body, dict):
        body = {}

    invite_id = body.get("invite_id")
    if not invite_id:
        return web.json_response({"error": "missing_invite_id", "message": "Invite ID required."}, status=400)

    from uuid import UUID
    from services.dungeon.dungeon_service import DungeonService

    dungeon_svc = DungeonService(db)

    # Hard guard: accepting an invite while already in another active run creates
    # split-state behavior (different users resolving different runs).
    # Require leaving current run before accepting a new invite.
    if char.get("in_dungeon"):
        return web.json_response(
            {"error": "already_in_dungeon", "message": "Leave your current dungeon party before accepting an invite."},
            status=400,
        )

    # Get invite
    invite = await db.fetchrow(
        """
        SELECT run_id, invitee_id, status FROM dungeon_party_invites WHERE id = $1
        """,
        invite_id,
    )
    if not invite:
        return web.json_response({"error": "invite_not_found", "message": "Invite not found."}, status=404)

    if str(invite["invitee_id"]) != str(char["id"]):
        return web.json_response({"error": "not_your_invite", "message": "This invite is not for you."}, status=403)

    if invite["status"] != "pending":
        return web.json_response({"error": "invite_already_used", "message": "This invite has already been used."}, status=400)

    # Check if run is still active
    run = await dungeon_svc.get_run(invite["run_id"])
    if not run or not run["is_active"]:
        return web.json_response({"error": "party_not_found", "message": "This party is no longer active."}, status=400)

    # Check party size
    if len(run["participants"]) >= 5:
        return web.json_response({"error": "party_full", "message": "This party is full."}, status=400)

    # Double-check active-run ownership via service (defense in depth).
    active_run = await dungeon_svc.get_active_run(char["id"])
    if active_run and str(active_run["id"]) != str(invite["run_id"]):
        return web.json_response(
            {"error": "already_in_dungeon", "message": "Leave your current dungeon party before accepting a new invite."},
            status=400,
        )

    # Add to party
    success = await dungeon_svc.add_participant(invite["run_id"], char["id"])
    if not success:
        return web.json_response(
            {"error": "join_failed", "message": "Failed to join party (already in another run, full, or invalid)."},
            status=400,
        )

    # Mark invite as accepted
    await db.execute(
        """
        UPDATE dungeon_party_invites SET status = 'accepted' WHERE id = $1
        """,
        invite_id,
    )

    run = await dungeon_svc.get_run(invite["run_id"])
    return web.json_response(_json_safe({
        "ok": True,
        "message": "Joined the party!",
        "run_id": str(run["id"]),
        "participants": run["participants"],
    }))


async def handle_dungeon_party_invite_decline(request: web.Request) -> web.Response:
    """POST /api/game/dungeon/party/invite/decline — Decline invite."""
    try:
        _user, discord_id, char, db = await _authed_discord_user_and_char(request)
    except web.HTTPException:
        raise
    if not char:
        return web.json_response({"error": "no_character", "message": "Create a character first."}, status=400)

    try:
        body = await request.json()
    except json.JSONDecodeError:
        body = {}
    if not isinstance(body, dict):
        body = {}

    invite_id = body.get("invite_id")
    if not invite_id:
        return web.json_response({"error": "missing_invite_id", "message": "Invite ID required."}, status=400)

    # Get invite
    invite = await db.fetchrow(
        """
        SELECT invitee_id, status FROM dungeon_party_invites WHERE id = $1
        """,
        invite_id,
    )
    if not invite:
        return web.json_response({"error": "invite_not_found", "message": "Invite not found."}, status=404)

    if str(invite["invitee_id"]) != str(char["id"]):
        return web.json_response({"error": "not_your_invite", "message": "This invite is not for you."}, status=403)

    # Mark as declined (or just delete)
    await db.execute(
        """
        DELETE FROM dungeon_party_invites WHERE id = $1
        """,
        invite_id,
    )

    return web.json_response({"ok": True, "message": "Invite declined."})


async def handle_dungeon_party_invite_cancel(request: web.Request) -> web.Response:
    """DELETE /api/game/dungeon/party/invite — Cancel outgoing invite (leader only)."""
    try:
        _user, discord_id, char, db = await _authed_discord_user_and_char(request)
    except web.HTTPException:
        raise
    if not char:
        return web.json_response({"error": "no_character", "message": "Create a character first."}, status=400)

    try:
        body = await request.json()
    except json.JSONDecodeError:
        body = {}
    if not isinstance(body, dict):
        body = {}

    invite_id = body.get("invite_id")
    if not invite_id:
        return web.json_response({"error": "missing_invite_id", "message": "Invite ID required."}, status=400)

    from services.dungeon.dungeon_service import DungeonService

    dungeon_svc = DungeonService(db)

    # Get invite
    invite = await db.fetchrow(
        """
        SELECT run_id, inviter_id FROM dungeon_party_invites WHERE id = $1
        """,
        invite_id,
    )
    if not invite:
        return web.json_response({"error": "invite_not_found", "message": "Invite not found."}, status=404)

    # Check if user is the inviter (leader)
    run = await dungeon_svc.get_run(invite["run_id"])
    if not run:
        return web.json_response({"error": "party_not_found", "message": "Party not found."}, status=404)

    is_leader = any(str(p["id"]) == str(char["id"]) and p.get("role") == "leader" for p in run["participants"])
    if not is_leader:
        return web.json_response({"error": "not_leader", "message": "Only the leader can cancel invites."}, status=403)

    # Delete invite
    await db.execute(
        """
        DELETE FROM dungeon_party_invites WHERE id = $1
        """,
        invite_id,
    )

    return web.json_response({"ok": True, "message": "Invite cancelled."})


async def handle_dungeon_party_enter(request: web.Request) -> web.Response:
    """POST /api/game/dungeon/party/enter — Enter dungeon combat (party mode)."""
    bot = request.app["bot"]
    db = getattr(bot, "db", None)
    if db is None or db.pool is None:
        raise web.HTTPServiceUnavailable(text=json.dumps({"error": "database_unavailable"}), content_type="application/json")

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise web.HTTPUnauthorized(text=json.dumps({"error": "missing_bearer"}), content_type="application/json")
    token = auth_header[7:].strip()

    user = await _user_from_bearer(token)
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

    from services.dungeon.dungeon_service import DungeonService
    from services.character.character_service import CharacterService
    from services.combat import activity_combat as activity_combat_api
    from config.settings import DUNGEONS

    char_svc = CharacterService(db)
    dungeon_svc = DungeonService(db)

    char = await char_svc.get_character(discord_id)
    if not char:
        return web.json_response({"error": "no_character", "message": "Create a character first."}, status=400)

    # Check if in a party (dungeon run)
    run = await dungeon_svc.get_active_run(char["id"])
    if not run:
        return web.json_response({"error": "not_in_party", "message": "You're not in a dungeon party. Create or join one first."}, status=400)

    # Match start_activity_combat: only real Discord /fight blocks us; stale Activity rows are cleared.
    if char.get("combat_status") == "in_combat":
        from services.combat.activity_combat import _char_in_discord_channel_combat

        if _char_in_discord_channel_combat(char["id"]):
            return web.json_response(
                {
                    "error": "in_discord_combat",
                    "message": "Finish your fight in Discord first, or wait for it to end.",
                },
                status=400,
            )
        await db.execute("UPDATE characters SET combat_status='idle' WHERE id=$1", char["id"])
        char = await char_svc.get_character(discord_id)
        if not char:
            return web.json_response({"error": "no_character", "message": "Create a character first."}, status=400)

    dungeon_config = DUNGEONS.get(run["dungeon_key"])
    if not dungeon_config:
        return web.json_response({"error": "invalid_dungeon", "message": "Invalid dungeon configuration."}, status=500)

    # Check level requirement
    if char["level"] < dungeon_config.level_req:
        return web.json_response({"error": "level_too_low", "message": f"Requires level {dungeon_config.level_req}."}, status=400)

    participants = run.get("participants") or []
    is_leader = any(
        str(p.get("id")) == str(char["id"]) and p.get("role") == "leader" for p in participants
    )
    if not is_leader:
        return web.json_response(
            {"error": "not_leader", "message": "Only the party leader can start the dungeon encounter."},
            status=403,
        )

    floor = run["current_floor"]
    run_id_uuid = run["id"]
    if run_id_uuid is None:
        return web.json_response({"error": "internal", "message": "Missing run id."}, status=500)

    if len(participants) >= 2:
        result = await activity_combat_api.start_party_dungeon_combat(
            bot, run_id_uuid, guild_id, discord_id
        )
    else:
        result = await activity_combat_api.start_activity_combat(
            bot, discord_id, guild_id,
            dungeon_key=run["dungeon_key"],
            dungeon_floor=floor,
            force=False,
        )

    if result.get("error"):
        err = result["error"]
        if err == "not_leader":
            status = 403
        elif err == "already_in_combat":
            status = 409
        else:
            status = 400
        return web.json_response(result, status=status)

    return web.json_response(_json_safe(result))


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

    user = await _user_from_bearer(token)
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

    user = await _user_from_bearer(token)
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

    # Compare as strings to handle UUID types correctly
    char_id_str = str(char["id"])
    is_leader = any(str(p["id"]) == char_id_str and p.get("role") == "leader" for p in run["participants"])
    
    # Debug logging
    import logging
    log = logging.getLogger("activity_http")
    log.debug(f"Dungeon party status: char_id={char_id_str}, participants={[{'id': str(p['id']), 'role': p.get('role')} for p in run['participants']]}, is_leader={is_leader}")
    
    return web.json_response(_json_safe({
        "ok": True,
        "in_party": True,
        "run_id": str(run["id"]),
        "is_leader": is_leader,
        "dungeon_key": run["dungeon_key"],
        "participants": run["participants"],
    }))


async def handle_combat_state(request: web.Request) -> web.Response:
    bot = request.app["bot"]
    db = getattr(bot, "db", None)
    if db is None or db.pool is None:
        raise web.HTTPServiceUnavailable(text=json.dumps({"error": "database_unavailable"}), content_type="application/json")

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise web.HTTPUnauthorized(text=json.dumps({"error": "missing_bearer"}), content_type="application/json")
    token = auth_header[7:].strip()

    user = await _user_from_bearer(token)
    if not user:
        raise web.HTTPUnauthorized(text=json.dumps({"error": "invalid_token"}), content_type="application/json")

    discord_id = int(user["id"])
    payload = await activity_combat_api.get_activity_combat_state(bot, discord_id)
    return web.json_response(_json_safe(payload))


async def handle_combat_state_ack(request: web.Request) -> web.Response:
    """POST — dismiss pending party/dungeon ended_outcome after the client applied it."""
    bot = request.app["bot"]
    db = getattr(bot, "db", None)
    if db is None or db.pool is None:
        raise web.HTTPServiceUnavailable(text=json.dumps({"error": "database_unavailable"}), content_type="application/json")

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise web.HTTPUnauthorized(text=json.dumps({"error": "missing_bearer"}), content_type="application/json")
    token = auth_header[7:].strip()

    user = await _user_from_bearer(token)
    if not user:
        raise web.HTTPUnauthorized(text=json.dumps({"error": "invalid_token"}), content_type="application/json")

    discord_id = int(user["id"])
    activity_combat_api.ack_party_pending_outcome(discord_id)
    return web.json_response(_json_safe({"ok": True}))


async def handle_combat_start(request: web.Request) -> web.Response:
    bot = request.app["bot"]
    db = getattr(bot, "db", None)
    if db is None or db.pool is None:
        raise web.HTTPServiceUnavailable(text=json.dumps({"error": "database_unavailable"}), content_type="application/json")

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise web.HTTPUnauthorized(text=json.dumps({"error": "missing_bearer"}), content_type="application/json")
    token = auth_header[7:].strip()

    user = await _user_from_bearer(token)
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

    char_svc = CharacterService(db)
    char = await char_svc.get_character(discord_id)
    if char and guild_id:
        await char_svc.set_last_discord_guild(char["id"], guild_id)

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
    elif result.get("error") == "party_dungeon_use_enter":
        status = 403
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

    user = await _user_from_bearer(token)
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
        status = 403 if result["error"] == "not_your_turn" else 400
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

    user = await _user_from_bearer(token)
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

    user = await _user_from_bearer(token)
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


async def handle_deeds(request: web.Request) -> web.Response:
    """GET — character deed flags for Activity (lore / Obsidian Silence)."""
    bot = request.app["bot"]
    db = getattr(bot, "db", None)
    if db is None or db.pool is None:
        raise web.HTTPServiceUnavailable(text=json.dumps({"error": "database_unavailable"}), content_type="application/json")

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise web.HTTPUnauthorized(text=json.dumps({"error": "missing_bearer"}), content_type="application/json")
    token = auth_header[7:].strip()

    user = await _user_from_bearer(token)
    if not user:
        raise web.HTTPUnauthorized(text=json.dumps({"error": "invalid_token"}), content_type="application/json")

    discord_id = int(user["id"])
    char_svc = CharacterService(db)
    char = await char_svc.get_character(discord_id)
    if not char:
        return web.json_response(_json_safe({"ok": True, "flags": []}))

    lg = LoreGateService(db)
    flags = await lg.get_flags(_uuid_from_any(char["id"]))
    return web.json_response(_json_safe({"ok": True, "flags": flags}))


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

    user = await _user_from_bearer(token)
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

    user = await _user_from_bearer(token)
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
    from services.talents.talent_service import TalentService

    talent_svc = TalentService(db)
    refund_info = await talent_svc.on_spec_chosen(
        _uuid_from_any(char["id"]), str(char.get("class") or ""), spec_key
    )
    state = await talent_svc.get_tree_state(await char_svc.get_by_id(char["id"]))
    return web.json_response(
        _json_safe({"ok": True, "message": msg, "spec_key": spec_key, "talents": state, **refund_info})
    )


async def _resolve_session(token: str) -> Optional[tuple[int, dict]]:
    """Resolve a bearer token to (player_id, user_dict).

    Tries our own session JWT first (local verify, no network) so standalone /
    mobile clients skip Discord; falls back to treating the token as a Discord
    bearer (the embedded Activity path — unchanged). `user_dict` is a
    Discord-user-shaped dict so existing handlers work for both. Returns None if
    neither path authenticates.
    """
    from services.auth.session_tokens import verify_session, identity_from_claims

    claims = verify_session(token)
    if claims is not None:
        return int(claims["sub"]), identity_from_claims(claims)

    discord_user = await _discord_user_from_token(token)
    if discord_user:
        return int(discord_user["id"]), discord_user
    return None


async def _user_from_bearer(token: str) -> Optional[dict]:
    """Session-aware replacement for inline `_discord_user_from_token(token)` in
    handlers: returns a Discord-user-shaped dict (id/username/...) for either our
    session JWT or a Discord bearer, or None. `user["id"]` is the player id."""
    resolved = await _resolve_session(token)
    return resolved[1] if resolved else None


async def _authed_discord_user_and_char(request: web.Request) -> tuple[dict, int, dict, Any]:
    bot = request.app["bot"]
    db = getattr(bot, "db", None)
    if db is None or db.pool is None:
        raise web.HTTPServiceUnavailable(text=json.dumps({"error": "database_unavailable"}), content_type="application/json")

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise web.HTTPUnauthorized(text=json.dumps({"error": "missing_bearer"}), content_type="application/json")
    token = auth_header[7:].strip()

    resolved = await _resolve_session(token)
    if not resolved:
        raise web.HTTPUnauthorized(text=json.dumps({"error": "invalid_token"}), content_type="application/json")
    player_id, user = resolved

    from services.social.social_service import SocialService

    await SocialService(db).touch_presence(player_id)
    char_svc = CharacterService(db)
    char = await char_svc.get_character(player_id)
    return user, player_id, dict(char) if char else None, db


async def _json_body(request: web.Request) -> dict:
    try:
        body = await request.json()
    except (json.JSONDecodeError, ValueError, TypeError):
        body = {}
    return body if isinstance(body, dict) else {}


async def handle_social_roster(request: web.Request) -> web.Response:
    try:
        _user, discord_id, char, db = await _authed_discord_user_and_char(request)
    except web.HTTPException:
        raise
    if not char:
        return web.json_response(_json_safe({"ok": False, "error": "no_character", "friends": []}), status=400)
    from services.social.social_service import SocialService

    try:
        svc = SocialService(db)
        friends = await svc.get_roster(discord_id)
        total_unread = await svc.get_total_unread(discord_id)
        return web.json_response(_json_safe({"ok": True, "friends": friends, "total_unread": total_unread}))
    except Exception as e:
        log.exception("handle_social_roster: %s", e)
        return web.json_response(
            _json_safe({"ok": False, "error": "social_unavailable", "friends": [], "total_unread": 0}),
            status=500,
        )


async def handle_social_requests(request: web.Request) -> web.Response:
    try:
        _user, discord_id, char, db = await _authed_discord_user_and_char(request)
    except web.HTTPException:
        raise
    if not char:
        return web.json_response(
            _json_safe({"ok": False, "error": "no_character", "incoming": [], "outgoing": []}),
            status=400,
        )
    from services.social.social_service import SocialService

    try:
        data = await SocialService(db).get_requests(discord_id)
        return web.json_response(_json_safe({"ok": True, **data}))
    except Exception as e:
        log.exception("handle_social_requests: %s", e)
        return web.json_response(
            _json_safe({"ok": False, "error": "social_unavailable", "incoming": [], "outgoing": []}),
            status=500,
        )


async def handle_social_players_search(request: web.Request) -> web.Response:
    try:
        _user, discord_id, char, db = await _authed_discord_user_and_char(request)
    except web.HTTPException:
        raise
    if not char:
        return web.json_response(_json_safe({"ok": False, "error": "no_character", "players": []}), status=400)
    q = str((request.query.get("q") or request.query.get("prefix") or "")).strip()
    purpose = str(request.query.get("purpose") or "friend").strip().lower()
    if purpose not in ("friend", "ignore"):
        purpose = "friend"
    from services.social.social_service import SocialService

    players = await SocialService(db).search_players(discord_id, q, purpose=purpose)
    return web.json_response(_json_safe({"ok": True, "players": players}))


async def handle_social_friend_request(request: web.Request) -> web.Response:
    try:
        _user, discord_id, char, db = await _authed_discord_user_and_char(request)
    except web.HTTPException:
        raise
    if not char:
        return web.json_response(_json_safe({"ok": False, "error": "no_character"}), status=400)
    body = await _json_body(request)
    from services.social.social_service import SocialService

    svc = SocialService(db)
    target_user_id = body.get("target_user_id")
    tid = int(target_user_id) if target_user_id else None
    ok, msg, data = await svc.send_friend_request(
        discord_id,
        username=str(body.get("username") or "") or None,
        target_user_id=tid,
    )
    return web.json_response(_json_safe({"ok": ok, "message": msg, **(data or {})}), status=200 if ok else 400)


async def handle_social_friend_accept(request: web.Request) -> web.Response:
    try:
        _user, discord_id, char, db = await _authed_discord_user_and_char(request)
    except web.HTTPException:
        raise
    if not char:
        return web.json_response(_json_safe({"ok": False, "error": "no_character"}), status=400)
    body = await _json_body(request)
    request_id = body.get("request_id")
    if not request_id:
        return web.json_response(_json_safe({"ok": False, "message": "request_id required"}), status=400)
    from services.social.social_service import SocialService

    ok, msg = await SocialService(db).accept_friend_request(discord_id, str(request_id))
    return web.json_response(_json_safe({"ok": ok, "message": msg}), status=200 if ok else 400)


async def handle_social_friend_decline(request: web.Request) -> web.Response:
    try:
        _user, discord_id, char, db = await _authed_discord_user_and_char(request)
    except web.HTTPException:
        raise
    if not char:
        return web.json_response(_json_safe({"ok": False, "error": "no_character"}), status=400)
    body = await _json_body(request)
    request_id = body.get("request_id")
    if not request_id:
        return web.json_response(_json_safe({"ok": False, "message": "request_id required"}), status=400)
    from services.social.social_service import SocialService

    ok, msg = await SocialService(db).decline_friend_request(discord_id, str(request_id))
    return web.json_response(_json_safe({"ok": ok, "message": msg}), status=200 if ok else 400)


async def handle_social_friend_delete(request: web.Request) -> web.Response:
    try:
        _user, discord_id, char, db = await _authed_discord_user_and_char(request)
    except web.HTTPException:
        raise
    if not char:
        return web.json_response(_json_safe({"ok": False, "error": "no_character"}), status=400)
    body = await _json_body(request)
    friend_user_id = body.get("friend_user_id")
    if not friend_user_id:
        return web.json_response(_json_safe({"ok": False, "message": "friend_user_id required"}), status=400)
    from services.social.social_service import SocialService

    ok, msg = await SocialService(db).unfriend(discord_id, int(friend_user_id))
    return web.json_response(_json_safe({"ok": ok, "message": msg}), status=200 if ok else 400)


async def handle_social_ignore_list(request: web.Request) -> web.Response:
    try:
        _user, discord_id, char, db = await _authed_discord_user_and_char(request)
    except web.HTTPException:
        raise
    if not char:
        return web.json_response(_json_safe({"ok": False, "error": "no_character", "ignored": []}), status=400)
    from services.social.social_service import SocialService

    ignored = await SocialService(db).list_ignores(discord_id)
    return web.json_response(_json_safe({"ok": True, "ignored": ignored}))


async def handle_social_ignore_add(request: web.Request) -> web.Response:
    try:
        _user, discord_id, char, db = await _authed_discord_user_and_char(request)
    except web.HTTPException:
        raise
    if not char:
        return web.json_response(_json_safe({"ok": False, "error": "no_character"}), status=400)
    body = await _json_body(request)
    from services.social.social_service import SocialService

    svc = SocialService(db)
    blocked_user_id = body.get("blocked_user_id")
    bid = int(blocked_user_id) if blocked_user_id else None
    ok, msg = await svc.add_ignore(
        discord_id,
        username=str(body.get("username") or "") or None,
        blocked_user_id=bid,
    )
    return web.json_response(_json_safe({"ok": ok, "message": msg}), status=200 if ok else 400)


async def handle_social_ignore_delete(request: web.Request) -> web.Response:
    try:
        _user, discord_id, char, db = await _authed_discord_user_and_char(request)
    except web.HTTPException:
        raise
    if not char:
        return web.json_response(_json_safe({"ok": False, "error": "no_character"}), status=400)
    body = await _json_body(request)
    blocked_user_id = body.get("blocked_user_id")
    if not blocked_user_id:
        return web.json_response(_json_safe({"ok": False, "message": "blocked_user_id required"}), status=400)
    from services.social.social_service import SocialService

    ok, msg = await SocialService(db).remove_ignore(discord_id, int(blocked_user_id))
    return web.json_response(_json_safe({"ok": ok, "message": msg}), status=200 if ok else 400)


async def handle_social_whispers_get(request: web.Request) -> web.Response:
    try:
        _user, discord_id, char, db = await _authed_discord_user_and_char(request)
    except web.HTTPException:
        raise
    if not char:
        return web.json_response(_json_safe({"ok": False, "error": "no_character", "messages": []}), status=400)
    with_user = request.query.get("with")
    if not with_user:
        return web.json_response(_json_safe({"ok": False, "message": "with query required"}), status=400)
    from services.social.social_service import SocialService

    messages = await SocialService(db).get_whispers(discord_id, int(with_user))
    return web.json_response(_json_safe({"ok": True, "messages": messages}))


async def handle_social_settings_get(request: web.Request) -> web.Response:
    try:
        _user, discord_id, char, db = await _authed_discord_user_and_char(request)
    except web.HTTPException:
        raise
    if not char:
        return web.json_response(_json_safe({"ok": False, "error": "no_character"}), status=400)
    from services.social.social_service import SocialService

    settings = await SocialService(db).get_settings(discord_id)
    return web.json_response(_json_safe({"ok": True, **settings}))


async def handle_social_settings_post(request: web.Request) -> web.Response:
    try:
        _user, discord_id, char, db = await _authed_discord_user_and_char(request)
    except web.HTTPException:
        raise
    if not char:
        return web.json_response(_json_safe({"ok": False, "error": "no_character"}), status=400)
    body = await _json_body(request)
    from services.social.social_service import SocialService

    appear = body.get("appear_offline")
    allow_whispers = body.get("allow_whispers_from_strangers")
    allow_party = body.get("allow_party_invites_from_strangers")
    settings = await SocialService(db).set_settings(
        discord_id,
        appear_offline=bool(appear) if appear is not None else None,
        allow_whispers_from_strangers=bool(allow_whispers) if allow_whispers is not None else None,
        allow_party_invites_from_strangers=bool(allow_party) if allow_party is not None else None,
    )
    return web.json_response(_json_safe({"ok": True, **settings}))


async def handle_social_friend_cancel(request: web.Request) -> web.Response:
    try:
        _user, discord_id, char, db = await _authed_discord_user_and_char(request)
    except web.HTTPException:
        raise
    if not char:
        return web.json_response(_json_safe({"ok": False, "error": "no_character"}), status=400)
    body = await _json_body(request)
    request_id = body.get("request_id")
    if not request_id:
        return web.json_response(_json_safe({"ok": False, "message": "request_id required"}), status=400)
    from services.social.social_service import SocialService

    ok, msg = await SocialService(db).cancel_friend_request(discord_id, str(request_id))
    return web.json_response(_json_safe({"ok": ok, "message": msg}), status=200 if ok else 400)


async def handle_social_suggestions(request: web.Request) -> web.Response:
    try:
        _user, discord_id, char, db = await _authed_discord_user_and_char(request)
    except web.HTTPException:
        raise
    if not char:
        return web.json_response(_json_safe({"ok": False, "error": "no_character", "suggestions": []}), status=400)
    try:
        from services.social.social_service import SocialService

        suggestions = await SocialService(db).get_suggestions(discord_id)
        return web.json_response(_json_safe({"ok": True, "suggestions": suggestions}))
    except Exception as e:
        log.exception("handle_social_suggestions: %s", e)
        return web.json_response(_json_safe({"ok": True, "suggestions": []}))


async def handle_social_whispers_inbox(request: web.Request) -> web.Response:
    try:
        _user, discord_id, char, db = await _authed_discord_user_and_char(request)
    except web.HTTPException:
        raise
    if not char:
        return web.json_response(_json_safe({"ok": False, "error": "no_character", "threads": []}), status=400)
    from services.social.social_service import SocialService

    threads = await SocialService(db).get_whisper_inbox(discord_id)
    return web.json_response(_json_safe({"ok": True, "threads": threads}))


async def handle_social_whisper_post(request: web.Request) -> web.Response:
    try:
        _user, discord_id, char, db = await _authed_discord_user_and_char(request)
    except web.HTTPException:
        raise
    if not char:
        return web.json_response(_json_safe({"ok": False, "error": "no_character"}), status=400)
    body = await _json_body(request)
    to_user_id = body.get("to_user_id")
    text = body.get("body")
    if not to_user_id:
        return web.json_response(_json_safe({"ok": False, "message": "to_user_id required"}), status=400)
    from services.social.social_service import SocialService

    ok, msg, data = await SocialService(db).send_whisper(discord_id, int(to_user_id), str(text or ""))
    return web.json_response(_json_safe({"ok": ok, "message": msg, **(data or {})}), status=200 if ok else 400)


async def handle_rest(request: web.Request) -> web.Response:
    """Full HP/resource restore — same rules as Discord /rest; clears Activity iframe combat if any."""
    bot = request.app["bot"]
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

    await activity_combat_api.dissolve_party_dungeon_combat_for_user(bot, discord_id)
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


async def handle_idle_rewards_get(request: web.Request) -> web.Response:
    """Preview pending idle XP/gold (no mutation)."""
    try:
        _user, _discord_id, char, _db = await _authed_discord_user_and_char(request)
    except web.HTTPException:
        raise
    if not char:
        return web.json_response(_json_safe({"ok": False, "error": "no_character"}), status=400)

    from services.activity_idle_rewards import compute_idle_pending, idle_pending_to_json

    pending = compute_idle_pending(dict(char))
    return web.json_response(_json_safe({"ok": True, **idle_pending_to_json(pending)}))


async def handle_idle_claim_post(request: web.Request) -> web.Response:
    """Claim accrued idle rewards (XP with rested/mult rules via CharacterService; gold with guild multipliers)."""
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

    from services.activity_idle_rewards import compute_idle_pending, idle_pending_to_json
    from services.reward_multipliers import get_combined_reward_multipliers

    char_svc = CharacterService(db)
    char_dict = dict(char)
    pending = compute_idle_pending(char_dict)

    if pending.pending_xp <= 0 and pending.pending_gold <= 0:
        return web.json_response(
            _json_safe(
                {
                    "ok": True,
                    "claimed": False,
                    "message": "Nothing to claim yet.",
                    **idle_pending_to_json(pending),
                }
            )
        )

    ig = _uuid_from_any(char_dict["guild_id"]) if char_dict.get("guild_id") else None
    xp_mult, gold_mult, _boss = await get_combined_reward_multipliers(db, guild_id, ingame_guild_id=ig)
    char_id = _uuid_from_any(char_dict["id"])

    xp_result: Dict[str, Any] = {}
    if pending.pending_xp > 0:
        xp_result = await char_svc.award_xp(char_id, pending.pending_xp, xp_mult)

    gold_gained = int(pending.pending_gold * gold_mult) if pending.pending_gold > 0 else 0
    if gold_gained > 0:
        await char_svc.add_gold(char_id, gold_gained, "idle rewards")

    await db.execute(
        "UPDATE characters SET idle_last_claim_at = NOW() WHERE id=$1",
        char_id,
    )

    fresh = await char_svc.get_character(discord_id)
    if fresh:
        fresh = CharacterService.normalize_resources(dict(fresh))

    after = compute_idle_pending(dict(fresh) if fresh else char_dict)
    return web.json_response(
        _json_safe(
            {
                "ok": True,
                "claimed": True,
                "xp_result": xp_result,
                "gold_gained": gold_gained,
                "character": dict(fresh) if fresh else None,
                **idle_pending_to_json(after),
            }
        )
    )


async def handle_repair_quote(request: web.Request) -> web.Response:
    """Cost to restore all equipped gear to full durability (no mutation)."""
    try:
        _user, _discord_id, char, db = await _authed_discord_user_and_char(request)
    except web.HTTPException:
        raise
    if not char:
        return web.json_response(_json_safe({"ok": False, "error": "no_character"}), status=400)

    inv_svc = InventoryService(db)
    total, items = await inv_svc.get_repair_quote(_uuid_from_any(char["id"]))
    return web.json_response(_json_safe({"ok": True, "total": total, "items": items, "gold": char.get("gold")}))


async def handle_repair_post(request: web.Request) -> web.Response:
    """Charge rarity-scaled gold and restore all equipped gear to 100 durability."""
    try:
        _user, discord_id, char, db = await _authed_discord_user_and_char(request)
    except web.HTTPException:
        raise
    if not char:
        return web.json_response(_json_safe({"ok": False, "error": "no_character"}), status=400)

    char_svc = CharacterService(db)
    inv_svc = InventoryService(db)
    char_id = _uuid_from_any(char["id"])
    # Quote + charge + repair happen in one transaction (no double-charge,
    # no gold eaten if the repair step fails).
    ok, err, total, items = await inv_svc.repair_all_charged(char_id)
    if ok and total <= 0:
        return web.json_response(_json_safe({"ok": True, "repaired": 0, "total": 0, "message": "Nothing to repair."}))
    if not ok:
        return web.json_response(
            _json_safe({"ok": False, "error": err or "insufficient_gold", "total": total}), status=400
        )
    fresh = await char_svc.get_character(discord_id)
    return web.json_response(_json_safe({
        "ok": True, "repaired": len(items), "total": total,
        "character": dict(fresh) if fresh else None,
    }))


async def handle_daily_quest_get(request: web.Request) -> web.Response:
    """Today's rotating daily quest (assigns one on first view)."""
    try:
        _user, _discord_id, char, db = await _authed_discord_user_and_char(request)
    except web.HTTPException:
        raise
    if not char:
        return web.json_response(_json_safe({"ok": False, "error": "no_character"}), status=400)

    from services.quest.daily_quest_service import DailyQuestService

    row = await DailyQuestService(db).get_or_assign_today(_uuid_from_any(char["id"]))
    if not row:
        return web.json_response(_json_safe({"ok": True, "quest": None}))
    return web.json_response(_json_safe({"ok": True, "quest": {
        "quest_id": row["quest_id"],
        "name": row["name"],
        "description": row["description"],
        "objectives": row["objectives"],
        "progress": row["progress"],
        "rewards": row["rewards"],
        "is_complete": row["is_complete"],
    }}))


async def handle_prestige_get(request: web.Request) -> web.Response:
    """Prestige eligibility + current bonus preview."""
    try:
        _user, _discord_id, char, db = await _authed_discord_user_and_char(request)
    except web.HTTPException:
        raise
    if not char:
        return web.json_response(_json_safe({"ok": False, "error": "no_character"}), status=400)

    from services.character.character_service import PRESTIGE_MAX, PRESTIGE_XP_BONUS

    prestige = int(char.get("prestige") or 0)
    return web.json_response(_json_safe({
        "ok": True,
        "prestige": prestige,
        "max": PRESTIGE_MAX,
        "xp_bonus_pct": round(PRESTIGE_XP_BONUS * prestige * 100, 1),
        "next_xp_bonus_pct": round(PRESTIGE_XP_BONUS * (prestige + 1) * 100, 1),
        "eligible": int(char.get("level") or 1) >= Settings.MAX_LEVEL and prestige < PRESTIGE_MAX,
        "required_level": Settings.MAX_LEVEL,
    }))


async def handle_prestige_post(request: web.Request) -> web.Response:
    """Execute prestige (requires {"confirm": true})."""
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
    if not isinstance(body, dict) or body.get("confirm") is not True:
        return web.json_response(_json_safe({"ok": False, "error": "confirm_required"}), status=400)

    char_svc = CharacterService(db)
    result = await char_svc.prestige_character(_uuid_from_any(char["id"]))
    if not result.get("ok"):
        return web.json_response(_json_safe(result), status=400)
    fresh = await char_svc.get_character(discord_id)
    return web.json_response(_json_safe({**result, "character": dict(fresh) if fresh else None}))


async def handle_trades_get(request: web.Request) -> web.Response:
    """Open trade offers involving this character (incoming + outgoing)."""
    try:
        _user, _discord_id, char, db = await _authed_discord_user_and_char(request)
    except web.HTTPException:
        raise
    if not char:
        return web.json_response(_json_safe({"ok": False, "error": "no_character"}), status=400)

    from services.trade.trade_service import TradeService

    svc = TradeService(db)
    await svc.expire_stale()
    rows = await svc.list_for(_uuid_from_any(char["id"]))
    me = str(char["id"])
    return web.json_response(_json_safe({
        "ok": True,
        "incoming": [r for r in rows if str(r["to_character"]) == me],
        "outgoing": [r for r in rows if str(r["from_character"]) == me],
    }))


async def handle_trade_offer_post(request: web.Request) -> web.Response:
    """Create a trade offer: JSON { target_user_id, item_id, gold_ask? }."""
    try:
        _user, _discord_id, char, db = await _authed_discord_user_and_char(request)
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

    target_user = str(body.get("target_user_id") or "").strip()
    item_id = _uuid_from_any(body.get("item_id"))
    try:
        gold_ask = max(0, int(body.get("gold_ask") or 0))
    except (TypeError, ValueError):
        gold_ask = 0
    if not target_user or not item_id:
        return web.json_response(_json_safe({"ok": False, "error": "bad_request"}), status=400)

    char_svc = CharacterService(db)
    try:
        target_char = await char_svc.get_character(int(target_user))
    except (TypeError, ValueError):
        target_char = None
    if not target_char:
        return web.json_response(_json_safe({"ok": False, "error": "target_no_character",
                                             "message": "That player has no character."}), status=400)

    from services.trade.trade_service import TradeService

    svc = TradeService(db)
    await svc.expire_stale()
    ok, msg, payload = await svc.create_offer(
        _uuid_from_any(char["id"]), _uuid_from_any(target_char["id"]), item_id, gold_ask
    )
    status = 200 if ok else 400
    return web.json_response(_json_safe({"ok": ok, "message": msg, "trade": payload}), status=status)


async def handle_trade_act_post(request: web.Request) -> web.Response:
    """Act on a trade: JSON { trade_id, action: accept | decline | cancel }."""
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

    trade_id = _uuid_from_any(body.get("trade_id"))
    action = str(body.get("action") or "").strip().lower()
    if not trade_id or action not in ("accept", "decline", "cancel"):
        return web.json_response(_json_safe({"ok": False, "error": "bad_request"}), status=400)

    from services.trade.trade_service import TradeService

    svc = TradeService(db)
    await svc.expire_stale()
    char_id = _uuid_from_any(char["id"])
    payload = None
    if action == "accept":
        ok, msg, payload = await svc.accept(trade_id, char_id)
    elif action == "decline":
        ok, msg = await svc.decline(trade_id, char_id)
    else:
        ok, msg = await svc.cancel(trade_id, char_id)

    fresh = await CharacterService(db).get_character(discord_id) if ok and action == "accept" else None
    return web.json_response(
        _json_safe({"ok": ok, "message": msg, "trade": payload,
                    "character": dict(fresh) if fresh else None}),
        status=200 if ok else 400,
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
    from services.social.social_service import SocialService

    try:
        target_discord_id = int(target)
    except (TypeError, ValueError):
        return web.json_response(_json_safe({"ok": False, "error": "invalid_target"}), status=400)
    if await SocialService(db).is_ignored(discord_id, target_discord_id):
        return web.json_response(
            _json_safe({"ok": False, "error": "blocked", "message": "You cannot challenge this player."}),
            status=400,
        )
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
    from services.social.social_service import _ignore_filter_sql

    rows = await db.fetch(
        f"""
        SELECT p.id, p.username
        FROM players p
        WHERE p.id != $1
          AND p.username IS NOT NULL
          AND p.username ILIKE $2
          {_ignore_filter_sql("$1")}
        ORDER BY p.username ASC
        LIMIT 12
        """,
        discord_id,
        q + "%",
    )
    players = [{"id": str(r["id"]), "username": str(r["username"])} for r in rows if r.get("username")]
    return web.json_response(_json_safe({"ok": True, "players": players}))


async def handle_dungeon_party_players(request: web.Request) -> web.Response:
    """Search players by username prefix for dungeon party invite autocomplete."""
    try:
        _user, discord_id, char, db = await _authed_discord_user_and_char(request)
    except web.HTTPException:
        raise
    if not char:
        return web.json_response(_json_safe({"ok": False, "error": "no_character", "players": []}), status=400)

    q = str((request.query.get("q") or "")).strip()
    if q.startswith("@"):
        q = q[1:].strip()
    if not q:
        # Return empty if no query - let UI show placeholder
        return web.json_response(_json_safe({"ok": True, "players": []}))

    q = q[:32]
    from services.social.social_service import _ignore_filter_sql

    rows = await db.fetch(
        f"""
        SELECT p.id, p.username, c.level, c.class
        FROM players p
        JOIN characters c ON c.player_id = p.id
        WHERE p.id != $1
          AND p.username IS NOT NULL
          AND c.is_active = TRUE
          AND c.in_dungeon = FALSE
          AND p.username ILIKE $2
          {_ignore_filter_sql("$1")}
        ORDER BY p.username ASC
        LIMIT 12
        """,
        discord_id,
        q + "%",
    )
    players = [
        {
            "id": str(r["id"]),
            "username": str(r["username"]),
            "level": r["level"],
            "class": r["class"],
        }
        for r in rows
        if r.get("username")
    ]
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

    guild_id = _guild_id_from_request(request, None)
    world_boss_windows: List[Dict[str, Any]] = []
    if guild_id:
        try:
            from services.world_boss.world_boss_service import WorldBossService

            world_boss_windows = await WorldBossService(db).list_active_windows(guild_id)
        except Exception:
            log.exception("handle_map world_boss_windows")

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
    return web.json_response(
        _json_safe({"zones": out, "current_zone": char.get("current_zone"), "world_boss_windows": world_boss_windows})
    )


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
        if quest_id is not None:
            quest_id = str(quest_id).strip()
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
        raw_state = q.get("state")
        state_norm = str(raw_state).strip().lower() if raw_state is not None else "active"
        out.append(
            {
                "quest_id": quest_id,
                "state": state_norm,
                "quest_name": q.get("quest_name"),
                "quest_desc": q.get("quest_desc"),
                "current_step": cur_step,
                "total_steps": q.get("total_steps"),
                "objective": objective,
                "completion_check": chk,
                "progress": progress,
                "expires_at": q.get("expires_at"),
                "lore_main": is_main_story_quest(quest_id),
                **(npc_info or {}),
            }
        )

    pointer = await qs.compute_main_story_pointer(
        char_id,
        int(char.get("level") or 1),
        str(char.get("current_zone") or "").strip() or None,
    )

    return web.json_response(_json_safe({"ok": True, "quests": out, "main_quest_pointer": pointer}))


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

    if is_main_story_quest(quest_id):
        return web.json_response(
            _json_safe(
                {
                    "ok": False,
                    "error": "main_story_locked",
                    "message": "Main story quests cannot be abandoned. Complete them or use an admin if you are truly stuck.",
                }
            ),
            status=403,
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

    guild_id = _guild_id_from_request(request, body)
    char_svc = CharacterService(db)

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

    if guild_id:
        await char_svc.set_last_discord_guild(_uuid_from_any(char["id"]), guild_id)

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

    if guild_id:
        await char_svc.set_last_discord_guild(_uuid_from_any(char["id"]), guild_id)

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
    from services.world_boss.world_boss_service import WorldBossService

    ig = _uuid_from_any(char["guild_id"]) if char.get("guild_id") else None
    xp_mult, gold_mult, boss_add = await get_combined_reward_multipliers(db, guild_id, ingame_guild_id=ig)
    wbs = WorldBossService(db)
    try:
        zone_patrol = await WorldBossService.fetch_zone_patrol_boss_alive(db, char.get("current_zone"))
    except Exception:
        zone_patrol = True  # safe default (matches world_boss_service.py:31)
    world_key = await wbs.active_window_boss_for_zone(guild_id, char.get("current_zone") or "")
    if world_key:
        boss_add = min(boss_add + 0.08, 0.15)
    outcome = roll_explore_outcome(
        zone,
        boss_add,
        zone_patrol_boss_alive=zone_patrol,
        world_boss_key=world_key,
    )

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
        # Gathering: crafting materials are farmable via exploration (parity with
        # /explore). Best-effort bonus — never fail the explore action over it.
        try:
            if random.random() < 0.35:
                scrap_tid = random.choice(("weapon_scrap", "armor_scrap", "accessory_scrap"))
                scrap_qty = random.randint(1, 2)
                ok_s, _ = await InventoryService(db).add_item(
                    _uuid_from_any(char["id"]), scrap_tid, "common", quantity=scrap_qty, from_="gathering"
                )
                if ok_s:
                    reward["scrap"] = {
                        "template_id": scrap_tid,
                        "name": scrap_tid.replace("_", " ").title(),
                        "quantity": scrap_qty,
                    }
        except Exception:
            log.warning("explore gathering scrap failed", exc_info=True)
    elif outcome["type"] == "safe":
        xp0 = random.randint(3, 8)
        xp_res = await char_svc.award_xp(_uuid_from_any(char["id"]), xp0, xp_mult)
        reward = {"xp": int(xp_res.get("xp_gained") or 0), "base_xp": xp0}

    # Daily quest progress (non-blocking)
    daily_line = None
    try:
        from services.quest.daily_quest_service import DailyQuestService
        daily_line = await DailyQuestService(db).record_event(
            char_svc, _uuid_from_any(char["id"]), "explore"
        )
    except Exception:
        pass

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
    if outcome["type"] in ("enemy", "boss", "loot"):
        try:
            from services.battle_pass.battle_pass_service import grant_explore_xp
            from services.guild import guild_quests as guild_quests_mod

            await grant_explore_xp(db, _uuid_from_any(char["id"]))
            if ig:
                await guild_quests_mod.record_event(db, ig, "explore", 1, _uuid_from_any(char["id"]))
        except Exception:
            pass

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
                "daily_quest_complete": daily_line,
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
        inv_svc = InventoryService(db)
        # Preflight inventory capacity before marking quest completed, so rewards are never silently lost.
        qid = str(talk_result.get("quest_id") or "")
        qtmpl = quest_svc._find_quest_template(qid) if qid else None
        reward_items = list(((qtmpl or {}).get("rewards") or {}).get("items") or [])
        if reward_items:
            can_add, add_msg = await inv_svc.can_add_reward_items(char_id, reward_items)
            if not can_add:
                return web.json_response(
                    _json_safe(
                        {
                            "ok": False,
                            "error": "reward_delivery_blocked",
                            "message": f"Cannot complete quest yet: {add_msg}",
                        }
                    ),
                    status=400,
                )

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
        granted_items: List[str] = []
        failed_items: List[Dict[str, str]] = []
        # Grant rewards (same semantics as /interact flow).
        xp_result: Dict[str, Any] = {}
        if rewards.get("xp"):
            xp_result = await char_svc.award_xp(char_id, int(rewards["xp"]))
        if rewards.get("gold"):
            await char_svc.add_gold(char_id, int(rewards["gold"]), "quest_reward", "quest_reward")
        if rewards.get("items"):
            for template_id in rewards["items"]:
                tmpl = await db.fetchrow("SELECT rarity FROM item_templates WHERE id = $1", template_id)
                rarity = tmpl["rarity"] if tmpl else "common"
                ok_add, msg_add = await inv_svc.add_item(char_id, template_id, rarity=rarity)
                if ok_add:
                    granted_items.append(str(template_id))
                else:
                    failed_items.append(
                        {
                            "template_id": str(template_id),
                            "reason": str(msg_add or "could_not_add"),
                        }
                    )
        char_level_loot = int((xp_result or {}).get("new_level") or char.get("level") or 1)
        zone_key_loot = str(char.get("current_zone") or "elwynn_forest")
        bonus_g, bonus_f = await inv_svc.grant_main_story_quest_gear_bonus_if_needed(
            char_id,
            is_main_story=is_main_story_quest(qid),
            template_item_reward_ids=reward_items,
            zone_key=zone_key_loot,
            char_level=char_level_loot,
        )
        granted_items.extend(bonus_g)
        failed_items.extend(bonus_f)
        if rewards.get("reputation"):
            for faction_id, amount in rewards["reputation"].items():
                await quest_svc.add_reputation(char_id, faction_id, int(amount))

        lore_gate = LoreGateService(db)
        if rewards.get("deed_flags"):
            await lore_gate.grant_deed_flags_from_rewards(char_id, rewards)

        completed_quest_ids = [q["quest_id"] for q in await quest_svc.get_completed_quests(char_id)]
        deed_set = set(await lore_gate.get_flags(char_id))
        next_quest = quest_svc.get_next_quest_for_npc(npc_id, completed_quest_ids, deed_set)
        reward_summary = {
            "xp": int(rewards.get("xp") or 0),
            "gold": int(rewards.get("gold") or 0),
            "items": granted_items,
            "item_failures": failed_items,
            "reputation": {k: int(v) for k, v in (rewards.get("reputation") or {}).items()},
        }
        completion_msg = (
            f"Quest complete. Some items could not be delivered ({len(failed_items)}): "
            + ", ".join(f.get("template_id", "?") for f in failed_items[:4])
            if failed_items
            else "Quest completed and rewards granted."
        )
        next_step_hint = "Continue exploring and talk to discovered NPCs for the next chain."
        pending_completion = {
            "quest_completed": True,
            "rewards": reward_summary,
            "message": completion_msg,
            "lore_main": is_main_story_quest(talk_result.get("quest_id")),
            "next_step_hint": next_step_hint,
        }
        from services.battle_pass.battle_pass_service import BattlePassService, XP_QUEST_COMPLETE

        bp = BattlePassService(db)
        await bp.try_grant_xp(char_id, f"quest_{qid}", XP_QUEST_COMPLETE, "quest_complete")
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
                            "next_step_hint": "No further quest from this NPC right now. Explore to discover more NPCs.",
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
                            "next_step_hint": "Level up via Explore/Combat, then press Talk on this same NPC.",
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
        deed_set = set(await LoreGateService(db).get_flags(char_id))
        next_quest = quest_svc.get_next_quest_for_npc(npc_id, completed_quest_ids, deed_set)
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
                            "message": "You already have this quest active. Finish it (or abandon side quests) before taking a new offer.",
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
            "lore_main": is_main_story_quest(next_quest.get("id")),
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
    user = await _user_from_bearer(token)
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
    user = await _user_from_bearer(token)
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
    user = await _user_from_bearer(token)
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

    if char.get("combat_status") == "in_combat":
        return web.json_response(
            {
                "ok": False,
                "error": "in_combat",
                "message": "You can't use items from inventory during a fight. Use the potion button in the combat UI.",
            },
            status=400,
        )

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

    user = await _user_from_bearer(token)
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
    user = await _user_from_bearer(token)
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
    user = await _user_from_bearer(token)
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


async def handle_shop_catalog(request: web.Request) -> web.Response:
    """Get available consumables from the vendor shop."""
    bot = request.app["bot"]
    db = getattr(bot, "db", None)
    if db is None or db.pool is None:
        raise web.HTTPServiceUnavailable(text=json.dumps({"error": "database_unavailable"}), content_type="application/json")

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise web.HTTPUnauthorized(text=json.dumps({"error": "missing_bearer"}), content_type="application/json")
    token = auth_header[7:].strip()
    user = await _user_from_bearer(token)
    if not user:
        raise web.HTTPUnauthorized(text=json.dumps({"error": "invalid_token"}), content_type="application/json")

    try:
        rows = await db.fetch(
            """SELECT id, name, icon, rarity, vendor_buy, effect_type, effect_value, effect_duration, level_req, description
               FROM item_templates
               WHERE vendor_buy IS NOT NULL AND vendor_buy > 0 AND item_type = 'consumable'
               ORDER BY level_req, vendor_buy"""
        )
        items = [dict(row) for row in rows]
        return web.json_response({"ok": True, "items": _json_safe(items)})
    except Exception as e:
        return web.json_response({"ok": False, "error": str(e), "message": "Failed to fetch shop catalog."}, status=500)


async def handle_shop_buy(request: web.Request) -> web.Response:
    """Buy a consumable item from the vendor shop."""
    bot = request.app["bot"]
    db = getattr(bot, "db", None)
    if db is None or db.pool is None:
        raise web.HTTPServiceUnavailable(text=json.dumps({"error": "database_unavailable"}), content_type="application/json")

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise web.HTTPUnauthorized(text=json.dumps({"error": "missing_bearer"}), content_type="application/json")
    token = auth_header[7:].strip()
    user = await _user_from_bearer(token)
    if not user:
        raise web.HTTPUnauthorized(text=json.dumps({"error": "invalid_token"}), content_type="application/json")

    try:
        body = await request.json()
    except json.JSONDecodeError:
        body = {}
    if not isinstance(body, dict):
        body = {}

    template_id = (body.get("template_id") or "").strip()
    qty = int(body.get("quantity") or 1)

    if not template_id or qty <= 0:
        return web.json_response({"ok": False, "error": "invalid_params", "message": "Missing or invalid template_id/quantity."}, status=400)

    discord_id = int(user["id"])
    char_svc = CharacterService(db)
    inv_svc = InventoryService(db)
    char = await char_svc.get_character(discord_id)
    if not char:
        return web.json_response({"ok": False, "error": "no_character", "message": "No character found."}, status=400)

    # Fetch template
    tmpl = await db.fetchrow("SELECT * FROM item_templates WHERE id=$1", template_id)
    if not tmpl:
        return web.json_response({"ok": False, "error": "not_found", "message": "Item not found."}, status=400)

    vendor_buy = int(tmpl["vendor_buy"] or 0)
    if vendor_buy <= 0:
        return web.json_response({"ok": False, "error": "not_for_sale", "message": "Item is not for sale."}, status=400)

    total_cost = vendor_buy * qty
    player_gold = int(char.get("gold") or 0)
    if player_gold < total_cost:
        return web.json_response(
            {"ok": False, "error": "insufficient_gold", "message": f"Not enough gold. Need {total_cost}, have {player_gold}."},
            status=400
        )

    # Deduct gold and add item
    ok = await char_svc.deduct_gold(char["id"], total_cost, f"vendor purchase x{qty}")
    if not ok:
        return web.json_response({"ok": False, "error": "deduct_failed", "message": "Failed to deduct gold."}, status=500)

    rarity = str(tmpl.get("rarity") or "common")
    add_ok, add_msg = await inv_svc.add_item(char["id"], template_id, rarity, qty, from_="vendor")
    if not add_ok:
        # Refund gold on item add failure
        await char_svc.add_gold(char["id"], total_cost, "refund: vendor purchase failed")
        return web.json_response({"ok": False, "error": "add_failed", "message": add_msg}, status=500)

    return web.json_response({"ok": True, "message": f"Purchased {tmpl['name']} x{qty}."})


async def handle_market_history(request: web.Request) -> web.Response:
    """GET /api/game/market/history — Recent market and auction trades for this character."""
    bot = request.app["bot"]
    db = getattr(bot, "db", None)
    if db is None or db.pool is None:
        raise web.HTTPServiceUnavailable(text=json.dumps({"error": "database_unavailable"}), content_type="application/json")

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise web.HTTPUnauthorized(text=json.dumps({"error": "missing_bearer"}), content_type="application/json")
    token = auth_header[7:].strip()
    user = await _user_from_bearer(token)
    if not user:
        raise web.HTTPUnauthorized(text=json.dumps({"error": "invalid_token"}), content_type="application/json")

    char_svc = CharacterService(db)
    char = await char_svc.get_character(int(user["id"]))
    if not char:
        return web.json_response(_json_safe({"ok": True, "entries": []}))

    try:
        lim = int(request.rel_url.query.get("limit") or 40)
    except (TypeError, ValueError):
        lim = 40

    from services.market.market_history import fetch_trade_history

    entries = await fetch_trade_history(db, _uuid_from_any(char["id"]), limit=lim)
    return web.json_response(_json_safe({"ok": True, "entries": entries}))


async def handle_milestones(request: web.Request) -> web.Response:
    """GET /api/game/milestones — Server milestone progress and active buffs."""
    bot = request.app["bot"]
    db = getattr(bot, "db", None)
    if db is None or db.pool is None:
        raise web.HTTPServiceUnavailable(text=json.dumps({"error": "database_unavailable"}), content_type="application/json")

    guild_id = _guild_id_from_request(request)
    if not guild_id:
        return web.json_response(
            _json_safe({"ok": False, "error": "missing_guild_id", "message": "Open the game in a Discord server."}),
            status=400,
        )

    from services.milestones.milestone_service import MilestoneService

    svc = MilestoneService(db)
    progress = await svc.get_progress(guild_id)
    buffs = await svc.get_active_buffs(guild_id)
    mult = await svc.get_active_multipliers(guild_id)
    return web.json_response(
        _json_safe(
            {
                "ok": True,
                "progress": progress,
                "buffs": buffs,
                "multipliers": mult,
            }
        )
    )


async def handle_reputation(request: web.Request) -> web.Response:
    """GET /api/game/reputation — Faction standings for the current character."""
    bot = request.app["bot"]
    db = getattr(bot, "db", None)
    if db is None or db.pool is None:
        raise web.HTTPServiceUnavailable(text=json.dumps({"error": "database_unavailable"}), content_type="application/json")

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise web.HTTPUnauthorized(text=json.dumps({"error": "missing_bearer"}), content_type="application/json")
    token = auth_header[7:].strip()
    user = await _user_from_bearer(token)
    if not user:
        raise web.HTTPUnauthorized(text=json.dumps({"error": "invalid_token"}), content_type="application/json")

    char_svc = CharacterService(db)
    char = await char_svc.get_character(int(user["id"]))
    if not char:
        return web.json_response(_json_safe({"ok": True, "factions": []}))

    from services.quest.npc_quest_service import NPCQuestService

    quest_svc = NPCQuestService(db)
    factions = await quest_svc.get_all_reputation(_uuid_from_any(char["id"]))
    return web.json_response(_json_safe({"ok": True, "factions": factions}))


async def handle_market_listings(request: web.Request) -> web.Response:
    """Get active player market listings."""
    bot = request.app["bot"]
    db = getattr(bot, "db", None)
    if db is None or db.pool is None:
        raise web.HTTPServiceUnavailable(text=json.dumps({"error": "database_unavailable"}), content_type="application/json")

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise web.HTTPUnauthorized(text=json.dumps({"error": "missing_bearer"}), content_type="application/json")
    token = auth_header[7:].strip()
    user = await _user_from_bearer(token)
    if not user:
        raise web.HTTPUnauthorized(text=json.dumps({"error": "invalid_token"}), content_type="application/json")

    try:
        rows = await db.fetch(
            """SELECT ml.id, ml.seller_id, ml.price, ml.quantity, ml.listed_at,
                      i.template_id,
                      it.equip_slot AS template_equip_slot,
                      it.item_type,
                      it.name, it.icon, it.description,
                      i.rarity, i.enhancement_level,
                      c.name AS seller_name
               FROM market_listings ml
               JOIN inventory i ON ml.item_id = i.id
               JOIN item_templates it ON i.template_id = it.id
               JOIN characters c ON ml.seller_id = c.id
               WHERE ml.is_active = TRUE AND ml.expires_at > NOW()
               AND COALESCE(ml.listing_kind, 'fixed') = 'fixed'
               ORDER BY ml.listed_at DESC
               LIMIT 50"""
        )
        listings = [dict(row) for row in rows]
        return web.json_response({"ok": True, "listings": _json_safe(listings)})
    except Exception as e:
        return web.json_response({"ok": False, "error": str(e), "message": "Failed to fetch market listings."}, status=500)


async def handle_list_item_on_market(request: web.Request) -> web.Response:
    """List a player-owned item on the marketplace."""
    bot = request.app["bot"]
    db = getattr(bot, "db", None)
    if db is None or db.pool is None:
        raise web.HTTPServiceUnavailable(text=json.dumps({"error": "database_unavailable"}), content_type="application/json")

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise web.HTTPUnauthorized(text=json.dumps({"error": "missing_bearer"}), content_type="application/json")
    token = auth_header[7:].strip()
    user = await _user_from_bearer(token)
    if not user:
        raise web.HTTPUnauthorized(text=json.dumps({"error": "invalid_token"}), content_type="application/json")

    try:
        body = await request.json()
    except json.JSONDecodeError:
        body = {}
    if not isinstance(body, dict):
        body = {}

    item_id = (body.get("item_id") or "").strip()
    price = int(body.get("price") or 0)

    if not item_id or price <= 0:
        return web.json_response(
            {"ok": False, "error": "invalid_params", "message": "Missing or invalid item_id/price."},
            status=400
        )

    discord_id = int(user["id"])
    char_svc = CharacterService(db)
    char = await char_svc.get_character(discord_id)
    if not char:
        return web.json_response({"ok": False, "error": "no_character", "message": "No character found."}, status=400)

    try:
        uid = UUID(item_id)
    except ValueError:
        return web.json_response({"ok": False, "error": "invalid_item_id", "message": "Invalid item id."}, status=400)

    # Check listing cap (max 10 active listings per player)
    active_count = await db.fetchval(
        "SELECT COUNT(*) FROM market_listings WHERE seller_id=$1 AND is_active=TRUE",
        char["id"]
    )
    if active_count >= 10:
        return web.json_response(
            {"ok": False, "error": "listing_cap_reached", "message": "You have reached the maximum of 10 active listings."},
            status=400
        )

    # Fetch item and validate
    inv_row = await db.fetchrow(
        """SELECT i.*, it.soulbound, it.tradeable, it.item_type, it.vendor_buy
           FROM inventory i
           JOIN item_templates it ON i.template_id = it.id
           WHERE i.id=$1 AND i.character_id=$2""",
        uid, char["id"]
    )

    if not inv_row:
        return web.json_response({"ok": False, "error": "item_not_found", "message": "Item not found in your inventory."}, status=400)

    # Validate item cannot be listed
    if inv_row["is_equipped"]:
        return web.json_response({"ok": False, "error": "item_equipped", "message": "Cannot list equipped items."}, status=400)

    if inv_row["soulbound"]:
        return web.json_response({"ok": False, "error": "item_soulbound", "message": "Cannot list soulbound items."}, status=400)

    if not inv_row["tradeable"]:
        return web.json_response({"ok": False, "error": "item_not_tradeable", "message": "This item cannot be traded."}, status=400)

    # Whitelist item types: only weapon, armor, accessory, material, gear
    item_type = (inv_row["item_type"] or "").lower()
    if item_type not in ("weapon", "armor", "accessory", "material", "gear"):
        return web.json_response(
            {"ok": False, "error": "item_type_not_listable", "message": f"Items of type '{item_type}' cannot be listed."},
            status=400
        )

    # Insert listing
    try:
        listing_id = await db.fetchval(
            """INSERT INTO market_listings (seller_id, item_id, price, quantity, is_active, listed_at, expires_at, listing_kind)
               VALUES ($1, $2, $3, 1, TRUE, NOW(), NOW() + INTERVAL '7 days', 'fixed')
               RETURNING id""",
            char["id"], uid, price
        )
        return web.json_response(
            {"ok": True, "listing_id": str(listing_id), "message": f"Listed for {price}g"},
            status=200
        )
    except Exception as e:
        return web.json_response(
            {"ok": False, "error": "listing_failed", "message": f"Failed to create listing: {str(e)}"},
            status=500
        )


class _MarketTxAbort(Exception):
    """Roll back a market transaction and return a JSON error to the Activity client."""
    def __init__(self, error: str, message: str, status: int = 400):
        super().__init__(message)
        self.error = error
        self.message = message
        self.status = status


async def handle_market_buy(request: web.Request) -> web.Response:
    """POST /api/game/market/buy — Buy a player listing (same logic as /market buy in Discord)."""
    bot = request.app["bot"]
    db = getattr(bot, "db", None)
    if db is None or db.pool is None:
        raise web.HTTPServiceUnavailable(text=json.dumps({"error": "database_unavailable"}), content_type="application/json")

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise web.HTTPUnauthorized(text=json.dumps({"error": "missing_bearer"}), content_type="application/json")
    token = auth_header[7:].strip()
    user = await _user_from_bearer(token)
    if not user:
        raise web.HTTPUnauthorized(text=json.dumps({"error": "invalid_token"}), content_type="application/json")

    try:
        body = await request.json()
    except json.JSONDecodeError:
        body = {}
    if not isinstance(body, dict):
        body = {}

    listing_id_raw = (body.get("listing_id") or body.get("id") or "").strip()
    if not listing_id_raw:
        return web.json_response(
            {"ok": False, "error": "missing_listing_id", "message": "Missing listing id."},
            status=400,
        )

    try:
        uid = UUID(listing_id_raw)
    except ValueError:
        return web.json_response(
            {"ok": False, "error": "invalid_listing_id", "message": "Invalid listing id."},
            status=400,
        )

    discord_id = int(user["id"])
    char_svc = CharacterService(db)
    char = await char_svc.get_character(discord_id)
    if not char:
        return web.json_response({"ok": False, "error": "no_character", "message": "No character found."}, status=400)

    # Atomic purchase: lock the listing row so concurrent buyers can't both pass the
    # is_active check (item dupe), and roll back gold if item delivery fails.
    try:
        async with db.transaction() as tx:
            listing = await tx.fetchrow(
                """SELECT ml.*, t.name, i.template_id,
                          i.rarity, i.r_str, i.r_agi, i.r_int, i.r_spi, i.r_sta,
                          i.r_haste, i.r_lifesteal, i.r_resistance, i.r_hit_rating,
                          COALESCE(i.enhancement_level, 0) as enhancement_level
                   FROM market_listings ml
                   JOIN inventory i ON ml.item_id = i.id
                   JOIN item_templates t ON i.template_id = t.id
                   WHERE ml.id = $1 AND ml.is_active = TRUE AND ml.expires_at > NOW()
                   AND COALESCE(ml.listing_kind, 'fixed') = 'fixed'
                   FOR UPDATE OF ml""",
                uid,
            )
            if not listing:
                raise _MarketTxAbort("listing_not_found", "Listing not found or expired.", 404)
            if listing["seller_id"] == char["id"]:
                raise _MarketTxAbort("own_listing", "You cannot buy your own listing.", 400)

            tx_char_svc = CharacterService(tx)
            inv = InventoryService(tx)

            price = int(listing["price"] or 0)
            paid = await tx_char_svc.deduct_gold(char["id"], price, "market purchase")
            if not paid:
                raise _MarketTxAbort("insufficient_gold", f"You need {price:,} gold.", 400)

            rarity = listing.get("rarity") or "common"
            bonus = {
                "r_str": listing.get("r_str", 0) or 0,
                "r_agi": listing.get("r_agi", 0) or 0,
                "r_int": listing.get("r_int", 0) or 0,
                "r_spi": listing.get("r_spi", 0) or 0,
                "r_sta": listing.get("r_sta", 0) or 0,
                "r_haste": listing.get("r_haste", 0) or 0,
                "r_lifesteal": listing.get("r_lifesteal", 0) or 0,
                "r_resistance": listing.get("r_resistance", 0) or 0,
                "r_hit_rating": listing.get("r_hit_rating", 0) or 0,
            }
            enhancement_level = listing.get("enhancement_level", 0) or 0
            add_ok, add_msg = await inv.add_item(
                char["id"],
                listing["template_id"],
                rarity=rarity,
                from_="market",
                bonus=bonus,
                enhancement_level=enhancement_level,
            )
            if not add_ok:
                # Rolls back the gold deduction — buyer keeps their gold, seller unpaid.
                raise _MarketTxAbort("transfer_failed", add_msg or "Could not add item to inventory.", 400)

            await tx_char_svc.add_gold(listing["seller_id"], price, "market sale")
            await tx.execute("DELETE FROM inventory WHERE id=$1", listing["item_id"])
            await tx.execute(
                "UPDATE market_listings SET is_active=FALSE, sold_at=NOW(), buyer_id=$2 WHERE id=$1",
                uid,
                char["id"],
            )
            bought_name, bought_price = listing["name"], price
    except _MarketTxAbort as e:
        return web.json_response({"ok": False, "error": e.error, "message": e.message}, status=e.status)

    return web.json_response(
        _json_safe(
            {
                "ok": True,
                "message": f"Purchased {bought_name} for {bought_price:,} gold.",
                "item_name": bought_name,
                "price": bought_price,
            }
        )
    )


async def _tx_deduct_gold(conn, char_id: UUID, amount: int, reason: str) -> bool:
    row = await conn.fetchrow(
        """UPDATE characters SET gold = gold - $2
           WHERE id = $1 AND gold >= $2
           RETURNING gold""",
        char_id,
        amount,
    )
    if not row:
        return False
    await conn.execute(
        """INSERT INTO gold_log(character_id, amount, balance_after, reason)
           VALUES ($1, $2, $3, $4)""",
        char_id,
        -amount,
        row["gold"],
        reason,
    )
    return True


async def _tx_add_gold(conn, char_id: UUID, amount: int, reason: str) -> None:
    row = await conn.fetchrow(
        """UPDATE characters SET gold = gold + $2 WHERE id = $1 RETURNING gold""",
        char_id,
        amount,
    )
    if not row:
        return
    await conn.execute(
        """INSERT INTO gold_log(character_id, amount, balance_after, reason)
           VALUES ($1, $2, $3, $4)""",
        char_id,
        amount,
        row["gold"],
        reason,
    )


async def handle_auction_listings(request: web.Request) -> web.Response:
    """GET active timed auctions."""
    bot = request.app["bot"]
    db = getattr(bot, "db", None)
    if db is None or db.pool is None:
        raise web.HTTPServiceUnavailable(text=json.dumps({"error": "database_unavailable"}), content_type="application/json")

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise web.HTTPUnauthorized(text=json.dumps({"error": "missing_bearer"}), content_type="application/json")
    token = auth_header[7:].strip()
    user = await _user_from_bearer(token)
    if not user:
        raise web.HTTPUnauthorized(text=json.dumps({"error": "invalid_token"}), content_type="application/json")

    try:
        await settle_expired_auctions(db, limit=80)
        rows = await db.fetch(
            """SELECT ml.id, ml.seller_id, ml.price, ml.quantity, ml.listed_at,
                      ml.buyout_price, ml.current_bid, ml.bid_count,
                      ml.auction_ends_at, ml.current_bidder_id,
                      i.template_id,
                      it.equip_slot AS template_equip_slot,
                      it.item_type,
                      it.name, it.icon, it.description,
                      i.rarity, i.enhancement_level,
                      c.name AS seller_name
               FROM market_listings ml
               JOIN inventory i ON ml.item_id = i.id
               JOIN item_templates it ON i.template_id = it.id
               JOIN characters c ON ml.seller_id = c.id
               WHERE ml.is_active = TRUE
                 AND COALESCE(ml.listing_kind, 'fixed') = 'auction'
                 AND ml.auction_ends_at IS NOT NULL
                 AND ml.auction_ends_at > NOW()
               ORDER BY ml.auction_ends_at ASC
               LIMIT 50"""
        )
        listings = []
        for row in rows:
            d = dict(row)
            start = int(d.get("price") or 0)
            cur = d.get("current_bid")
            cur_int = int(cur) if cur is not None else None
            d["min_bid"] = auction_min_bid(start, cur_int)
            listings.append(d)
        return web.json_response({"ok": True, "listings": _json_safe(listings)})
    except Exception as e:
        return web.json_response(
            {"ok": False, "error": str(e), "message": "Failed to fetch auction listings."},
            status=500,
        )


async def handle_auction_create(request: web.Request) -> web.Response:
    """POST create timed auction listing."""
    bot = request.app["bot"]
    db = getattr(bot, "db", None)
    if db is None or db.pool is None:
        raise web.HTTPServiceUnavailable(text=json.dumps({"error": "database_unavailable"}), content_type="application/json")

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise web.HTTPUnauthorized(text=json.dumps({"error": "missing_bearer"}), content_type="application/json")
    token = auth_header[7:].strip()
    user = await _user_from_bearer(token)
    if not user:
        raise web.HTTPUnauthorized(text=json.dumps({"error": "invalid_token"}), content_type="application/json")

    try:
        body = await request.json()
    except json.JSONDecodeError:
        body = {}
    if not isinstance(body, dict):
        body = {}

    item_id_raw = (body.get("item_id") or "").strip()
    starting_bid = int(body.get("starting_bid") or body.get("price") or 0)
    duration_hours = int(body.get("duration_hours") or 72)
    buyout_raw = body.get("buyout_price")
    buyout_price: Optional[int] = None
    if buyout_raw is not None and str(buyout_raw).strip() != "":
        buyout_price = int(buyout_raw)

    if not item_id_raw or starting_bid <= 0:
        return web.json_response(
            {"ok": False, "error": "invalid_params", "message": "Missing or invalid item_id/starting_bid."},
            status=400,
        )

    duration_hours = max(24, min(168, duration_hours))

    if buyout_price is not None:
        if buyout_price < starting_bid:
            return web.json_response(
                {"ok": False, "error": "invalid_buyout", "message": "Buyout must be at least the starting bid."},
                status=400,
            )

    discord_id = int(user["id"])
    char_svc = CharacterService(db)
    char = await char_svc.get_character(discord_id)
    if not char:
        return web.json_response({"ok": False, "error": "no_character", "message": "No character found."}, status=400)

    try:
        uid = UUID(item_id_raw)
    except ValueError:
        return web.json_response({"ok": False, "error": "invalid_item_id", "message": "Invalid item id."}, status=400)

    active_count = await db.fetchval(
        "SELECT COUNT(*) FROM market_listings WHERE seller_id=$1 AND is_active=TRUE",
        char["id"],
    )
    if active_count >= 10:
        return web.json_response(
            {"ok": False, "error": "listing_cap_reached", "message": "You have reached the maximum of 10 active listings."},
            status=400,
        )

    inv_row = await db.fetchrow(
        """SELECT i.*, it.soulbound, it.tradeable, it.item_type
           FROM inventory i
           JOIN item_templates it ON i.template_id = it.id
           WHERE i.id=$1 AND i.character_id=$2""",
        uid,
        char["id"],
    )
    if not inv_row:
        return web.json_response({"ok": False, "error": "item_not_found", "message": "Item not found in your inventory."}, status=400)
    if inv_row["is_equipped"]:
        return web.json_response({"ok": False, "error": "item_equipped", "message": "Cannot list equipped items."}, status=400)
    if inv_row["soulbound"]:
        return web.json_response({"ok": False, "error": "item_soulbound", "message": "Cannot list soulbound items."}, status=400)
    if not inv_row["tradeable"]:
        return web.json_response({"ok": False, "error": "item_not_tradeable", "message": "This item cannot be traded."}, status=400)
    item_type = (inv_row["item_type"] or "").lower()
    if item_type not in ("weapon", "armor", "accessory", "material", "gear"):
        return web.json_response(
            {"ok": False, "error": "item_type_not_listable", "message": f"Items of type '{item_type}' cannot be listed."},
            status=400,
        )

    try:
        listing_id = await db.fetchval(
            """INSERT INTO market_listings (
                   seller_id, item_id, price, quantity, is_active, listed_at, expires_at,
                   listing_kind, buyout_price, auction_ends_at, bid_count, current_bid, current_bidder_id
               )
               VALUES (
                   $1, $2, $3, 1, TRUE, NOW(), NOW() + make_interval(hours => $4::int),
                   'auction', $5, NOW() + make_interval(hours => $4::int), 0, NULL, NULL
               )
               RETURNING id""",
            char["id"],
            uid,
            starting_bid,
            str(duration_hours),
            buyout_price,
        )
        return web.json_response(
            {"ok": True, "listing_id": str(listing_id), "message": f"Auction started (opens at {starting_bid}g)."},
            status=200,
        )
    except Exception as e:
        return web.json_response(
            {"ok": False, "error": "listing_failed", "message": f"Failed to create auction: {str(e)}"},
            status=500,
        )


async def handle_auction_bid(request: web.Request) -> web.Response:
    """POST place gold bid on auction."""
    bot = request.app["bot"]
    db = getattr(bot, "db", None)
    if db is None or db.pool is None:
        raise web.HTTPServiceUnavailable(text=json.dumps({"error": "database_unavailable"}), content_type="application/json")

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise web.HTTPUnauthorized(text=json.dumps({"error": "missing_bearer"}), content_type="application/json")
    token = auth_header[7:].strip()
    user = await _user_from_bearer(token)
    if not user:
        raise web.HTTPUnauthorized(text=json.dumps({"error": "invalid_token"}), content_type="application/json")

    try:
        body = await request.json()
    except json.JSONDecodeError:
        body = {}
    if not isinstance(body, dict):
        body = {}

    listing_id_raw = (body.get("listing_id") or body.get("id") or "").strip()
    amount = int(body.get("amount") or 0)
    if not listing_id_raw or amount <= 0:
        return web.json_response(
            {"ok": False, "error": "invalid_params", "message": "Missing listing id or invalid bid amount."},
            status=400,
        )

    try:
        lid = UUID(listing_id_raw)
    except ValueError:
        return web.json_response({"ok": False, "error": "invalid_listing_id", "message": "Invalid listing id."}, status=400)

    discord_id = int(user["id"])
    char_svc = CharacterService(db)
    char = await char_svc.get_character(discord_id)
    if not char:
        return web.json_response({"ok": False, "error": "no_character", "message": "No character found."}, status=400)

    await settle_expired_auctions(db, limit=40)

    try:
        async with db.pool.acquire() as conn:
            async with conn.transaction():
                ml = await conn.fetchrow(
                    """SELECT * FROM market_listings WHERE id = $1 FOR UPDATE""",
                    lid,
                )
                if not ml or not ml["is_active"]:
                    return web.json_response(
                        {"ok": False, "error": "listing_not_found", "message": "Listing not found or closed."},
                        status=404,
                    )
                if (ml.get("listing_kind") or "fixed") != "auction":
                    return web.json_response(
                        {"ok": False, "error": "not_auction", "message": "This is not an auction listing."},
                        status=400,
                    )
                if ml["seller_id"] == char["id"]:
                    return web.json_response(
                        {"ok": False, "error": "own_listing", "message": "You cannot bid on your own auction."},
                        status=400,
                    )
                ends_at = ml["auction_ends_at"]
                if ends_at is None:
                    return web.json_response(
                        {"ok": False, "error": "invalid_listing", "message": "Auction has no end time."},
                        status=400,
                    )
                now = datetime.now(timezone.utc)
                if ends_at.tzinfo is None:
                    ends_at = ends_at.replace(tzinfo=timezone.utc)
                if ends_at <= now:
                    return web.json_response(
                        {"ok": False, "error": "auction_ended", "message": "This auction has ended."},
                        status=400,
                    )

                start = int(ml["price"] or 0)
                cur = ml["current_bid"]
                cur_int = int(cur) if cur is not None else None
                min_bid = auction_min_bid(start, cur_int)
                if amount < min_bid:
                    return web.json_response(
                        {
                            "ok": False,
                            "error": "bid_too_low",
                            "message": f"Minimum bid is {min_bid:,} gold.",
                            "min_bid": min_bid,
                        },
                        status=400,
                    )

                bo = ml["buyout_price"]
                if bo is not None and int(bo) > 0 and amount >= int(bo):
                    return web.json_response(
                        {
                            "ok": False,
                            "error": "use_buyout",
                            "message": "That amount meets or exceeds buyout — use buyout instead.",
                            "buyout_price": int(bo),
                        },
                        status=400,
                    )

                prev_bidder = ml["current_bidder_id"]
                prev_amt = ml["current_bid"]
                prev_amt_int = int(prev_amt) if prev_amt is not None else None

                if prev_bidder is None:
                    ok = await _tx_deduct_gold(conn, char["id"], amount, "auction bid")
                    if not ok:
                        return web.json_response(
                            {"ok": False, "error": "insufficient_gold", "message": f"You need at least {amount:,} gold."},
                            status=400,
                        )
                elif prev_bidder == char["id"]:
                    if prev_amt_int is None:
                        return web.json_response({"ok": False, "error": "invalid_state", "message": "Invalid auction state."}, status=400)
                    delta = amount - prev_amt_int
                    if delta <= 0:
                        return web.json_response(
                            {"ok": False, "error": "bid_too_low", "message": "Your new bid must be higher than your current bid."},
                            status=400,
                        )
                    ok = await _tx_deduct_gold(conn, char["id"], delta, "auction bid raise")
                    if not ok:
                        return web.json_response(
                            {"ok": False, "error": "insufficient_gold", "message": f"You need at least {delta:,} more gold."},
                            status=400,
                        )
                else:
                    ok = await _tx_deduct_gold(conn, char["id"], amount, "auction bid")
                    if not ok:
                        return web.json_response(
                            {"ok": False, "error": "insufficient_gold", "message": f"You need at least {amount:,} gold."},
                            status=400,
                        )
                    if prev_bidder is not None and prev_amt_int is not None:
                        await _tx_add_gold(conn, prev_bidder, prev_amt_int, "auction outbid refund")

                new_ends = maybe_extend_auction_end(ends_at, now)
                await conn.execute(
                    """UPDATE market_listings SET
                           current_bid = $1,
                           current_bidder_id = $2,
                           bid_count = bid_count + 1,
                           auction_ends_at = $3,
                           expires_at = $3
                       WHERE id = $4""",
                    amount,
                    char["id"],
                    new_ends,
                    lid,
                )

        return web.json_response(
            {
                "ok": True,
                "message": f"Bid placed: {amount:,} gold.",
                "bid": amount,
            }
        )
    except Exception as e:
        return web.json_response(
            {"ok": False, "error": str(e), "message": "Failed to place bid."},
            status=500,
        )


async def _transfer_listing_item_to_buyer(
    db,
    listing_row: dict,
    buyer_char_id: UUID,
    template_id: str,
    rarity: str,
    bonus: dict,
    enhancement_level: int,
    from_: str,
) -> tuple[bool, str]:
    """Give listed item copy to buyer and delete listed inventory row (auction buyout)."""
    inv = InventoryService(db)
    char_svc = CharacterService(db)
    seller_id = listing_row["seller_id"]
    pay = int(listing_row["pay_seller"])
    await char_svc.add_gold(seller_id, pay, "market sale")
    add_ok, add_msg = await inv.add_item(
        buyer_char_id,
        template_id,
        rarity=rarity,
        from_=from_,
        bonus=bonus,
        enhancement_level=enhancement_level,
    )
    if not add_ok:
        await char_svc.deduct_gold(seller_id, pay, "revert: market transfer failed")
        return False, add_msg or "Could not add item to inventory."
    await db.execute("DELETE FROM inventory WHERE id=$1", listing_row["item_id"])
    await db.execute(
        "UPDATE market_listings SET is_active=FALSE, sold_at=NOW(), buyer_id=$2 WHERE id=$1",
        listing_row["id"],
        buyer_char_id,
    )
    return True, "ok"


async def handle_auction_buyout(request: web.Request) -> web.Response:
    """POST instant purchase at buyout price."""
    bot = request.app["bot"]
    db = getattr(bot, "db", None)
    if db is None or db.pool is None:
        raise web.HTTPServiceUnavailable(text=json.dumps({"error": "database_unavailable"}), content_type="application/json")

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise web.HTTPUnauthorized(text=json.dumps({"error": "missing_bearer"}), content_type="application/json")
    token = auth_header[7:].strip()
    user = await _user_from_bearer(token)
    if not user:
        raise web.HTTPUnauthorized(text=json.dumps({"error": "invalid_token"}), content_type="application/json")

    try:
        body = await request.json()
    except json.JSONDecodeError:
        body = {}
    if not isinstance(body, dict):
        body = {}

    listing_id_raw = (body.get("listing_id") or body.get("id") or "").strip()
    if not listing_id_raw:
        return web.json_response({"ok": False, "error": "missing_listing_id", "message": "Missing listing id."}, status=400)

    try:
        lid = UUID(listing_id_raw)
    except ValueError:
        return web.json_response({"ok": False, "error": "invalid_listing_id", "message": "Invalid listing id."}, status=400)

    discord_id = int(user["id"])
    char_svc = CharacterService(db)
    char = await char_svc.get_character(discord_id)
    if not char:
        return web.json_response({"ok": False, "error": "no_character", "message": "No character found."}, status=400)

    await settle_expired_auctions(db, limit=40)

    listing = await db.fetchrow(
        """SELECT ml.*, t.name, i.template_id,
                  i.rarity, i.r_str, i.r_agi, i.r_int, i.r_spi, i.r_sta,
                  i.r_haste, i.r_lifesteal, i.r_resistance, i.r_hit_rating,
                  COALESCE(i.enhancement_level, 0) AS enhancement_level
           FROM market_listings ml
           JOIN inventory i ON ml.item_id = i.id
           JOIN item_templates t ON i.template_id = t.id
           WHERE ml.id = $1 AND ml.is_active = TRUE
             AND COALESCE(ml.listing_kind, 'fixed') = 'auction'
             AND ml.auction_ends_at IS NOT NULL AND ml.auction_ends_at > NOW()""",
        lid,
    )
    if not listing:
        return web.json_response(
            {"ok": False, "error": "listing_not_found", "message": "Listing not found, expired, or not an auction."},
            status=404,
        )
    if listing["seller_id"] == char["id"]:
        return web.json_response(
            {"ok": False, "error": "own_listing", "message": "You cannot buy out your own auction."},
            status=400,
        )
    bp = listing["buyout_price"]
    if bp is None or int(bp) <= 0:
        return web.json_response(
            {"ok": False, "error": "no_buyout", "message": "This auction has no buyout price."},
            status=400,
        )
    buyout = int(bp)

    prev_bidder = listing["current_bidder_id"]
    prev_amt = int(listing["current_bid"]) if listing["current_bid"] is not None else None

    if prev_bidder is not None and prev_amt is not None:
        await char_svc.add_gold(prev_bidder, prev_amt, "auction outbid refund")

    paid = await char_svc.deduct_gold(char["id"], buyout, "auction buyout")
    if not paid:
        if prev_bidder is not None and prev_amt is not None:
            await char_svc.deduct_gold(prev_bidder, prev_amt, "revert: buyout could not be paid")
        return web.json_response(
            {"ok": False, "error": "insufficient_gold", "message": f"You need {buyout:,} gold."},
            status=400,
        )

    rarity = listing.get("rarity") or "common"
    bonus = {
        "r_str": listing.get("r_str", 0) or 0,
        "r_agi": listing.get("r_agi", 0) or 0,
        "r_int": listing.get("r_int", 0) or 0,
        "r_spi": listing.get("r_spi", 0) or 0,
        "r_sta": listing.get("r_sta", 0) or 0,
        "r_haste": listing.get("r_haste", 0) or 0,
        "r_lifesteal": listing.get("r_lifesteal", 0) or 0,
        "r_resistance": listing.get("r_resistance", 0) or 0,
        "r_hit_rating": listing.get("r_hit_rating", 0) or 0,
    }
    enhancement_level = listing.get("enhancement_level", 0) or 0

    row = dict(listing)
    row["pay_seller"] = buyout
    ok, msg = await _transfer_listing_item_to_buyer(
        db,
        row,
        char["id"],
        listing["template_id"],
        rarity,
        bonus,
        enhancement_level,
        "auction",
    )
    if not ok:
        await char_svc.add_gold(char["id"], buyout, "refund: auction buyout failed")
        if prev_bidder is not None and prev_amt is not None:
            await char_svc.deduct_gold(prev_bidder, prev_amt, "revert: buyout refund after transfer failure")
        return web.json_response({"ok": False, "error": "transfer_failed", "message": msg}, status=400)

    return web.json_response(
        _json_safe(
            {
                "ok": True,
                "message": f"Buyout: {listing['name']} for {buyout:,} gold.",
                "item_name": listing["name"],
                "price": buyout,
            }
        )
    )


async def handle_auction_cancel(request: web.Request) -> web.Response:
    """POST cancel auction with no bids (seller only)."""
    bot = request.app["bot"]
    db = getattr(bot, "db", None)
    if db is None or db.pool is None:
        raise web.HTTPServiceUnavailable(text=json.dumps({"error": "database_unavailable"}), content_type="application/json")

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise web.HTTPUnauthorized(text=json.dumps({"error": "missing_bearer"}), content_type="application/json")
    token = auth_header[7:].strip()
    user = await _user_from_bearer(token)
    if not user:
        raise web.HTTPUnauthorized(text=json.dumps({"error": "invalid_token"}), content_type="application/json")

    try:
        body = await request.json()
    except json.JSONDecodeError:
        body = {}
    if not isinstance(body, dict):
        body = {}

    listing_id_raw = (body.get("listing_id") or body.get("id") or "").strip()
    if not listing_id_raw:
        return web.json_response({"ok": False, "error": "missing_listing_id", "message": "Missing listing id."}, status=400)

    try:
        lid = UUID(listing_id_raw)
    except ValueError:
        return web.json_response({"ok": False, "error": "invalid_listing_id", "message": "Invalid listing id."}, status=400)

    discord_id = int(user["id"])
    char_svc = CharacterService(db)
    char = await char_svc.get_character(discord_id)
    if not char:
        return web.json_response({"ok": False, "error": "no_character", "message": "No character found."}, status=400)

    res = await db.execute(
        """UPDATE market_listings SET is_active = FALSE
           WHERE id = $1 AND seller_id = $2 AND is_active = TRUE
             AND COALESCE(listing_kind, 'fixed') = 'auction'
             AND bid_count = 0""",
        lid,
        char["id"],
    )
    if res == "UPDATE 0":
        return web.json_response(
            {"ok": False, "error": "cannot_cancel", "message": "Cannot cancel (not your auction, has bids, or already closed)."},
            status=400,
        )
    return web.json_response({"ok": True, "message": "Auction cancelled. Item is available in your inventory again."})


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
    user = await _user_from_bearer(token)
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


# ── Guild hub (in-game UUID guild) ───────────────────────────────────────────


async def handle_guild_create(request: web.Request) -> web.Response:
    """POST — create a new in-game guild (same rules as ``/guild create``). Requires Discord server id (``X-Guild-Id`` or JSON ``guild_id``)."""
    try:
        _user, discord_id, char, db = await _authed_discord_user_and_char(request)
    except web.HTTPException:
        raise
    if not char:
        return web.json_response(
            _json_safe({"ok": False, "error": "no_character", "message": "Create a character first."}),
            status=400,
        )
    if char.get("guild_id"):
        return web.json_response(
            _json_safe({"ok": False, "error": "already_in_guild", "message": "You're already in a guild."}),
            status=400,
        )

    try:
        body = await request.json()
    except json.JSONDecodeError:
        body = {}
    if not isinstance(body, dict):
        body = {}

    server_id = _guild_id_from_request(request, body)
    if not server_id:
        return web.json_response(
            _json_safe(
                {
                    "ok": False,
                    "error": "missing_discord_guild",
                    "message": "Open this Activity from your Discord server so we know which realm to register the hall under.",
                }
            ),
            status=400,
        )

    raw_name = body.get("name")
    raw_tag = body.get("tag")
    name = raw_name.strip() if isinstance(raw_name, str) else ""
    tag = raw_tag.upper().strip() if isinstance(raw_tag, str) else ""

    if not (2 <= len(tag) <= 8) or not tag.isalnum():
        return web.json_response(
            _json_safe({"ok": False, "error": "invalid_tag", "message": "Tag must be 2–8 alphanumeric characters."}),
            status=400,
        )
    if not (3 <= len(name) <= 64):
        return web.json_response(
            _json_safe({"ok": False, "error": "invalid_name", "message": "Guild name must be 3–64 characters."}),
            status=400,
        )

    exists = await db.fetchrow("SELECT id FROM guilds WHERE name ILIKE $1 OR tag=$2", name, tag)
    if exists:
        return web.json_response(
            _json_safe({"ok": False, "error": "taken", "message": "That name or tag is already taken."}),
            status=400,
        )

    char_uuid = _uuid_from_any(char["id"])
    try:
        guild = await db.fetchrow(
            "INSERT INTO guilds(name,tag,guildmaster_id,server_id) VALUES($1,$2,$3,$4) RETURNING *",
            name,
            tag,
            char_uuid,
            server_id,
        )
    except Exception as e:
        log.warning("guild create insert failed: %s", e)
        return web.json_response(
            _json_safe(
                {
                    "ok": False,
                    "error": "create_failed",
                    "message": "Could not create guild (name or tag may be taken).",
                }
            ),
            status=400,
        )

    await db.execute(
        "UPDATE characters SET guild_id=$2, guild_rank='guildmaster' WHERE id=$1",
        char_uuid,
        guild["id"],
    )

    try:
        ach_svc = AchievementService(db)
        await ach_svc.check_and_award(char_uuid, "guild_create", {})
    except Exception as e:
        log.debug("guild create achievement: %s", e)

    return web.json_response(
        _json_safe(
            {
                "ok": True,
                "message": f"Founded **[{tag}] {name}**! You are guildmaster.",
                "guild": {"id": str(guild["id"]), "name": guild["name"], "tag": guild["tag"]},
            }
        )
    )


async def handle_guild_me(request: web.Request) -> web.Response:
    try:
        _user, discord_id, char, db = await _authed_discord_user_and_char(request)
    except web.HTTPException:
        raise
    if not char:
        return web.json_response(_json_safe({"ok": False, "error": "no_character"}), status=400)
    if not char.get("guild_id"):
        return web.json_response(
            _json_safe(
                {
                    "ok": True,
                    "in_guild": False,
                    "message": "Found a hall from this tab, or use Discord /guild create. Join via an officer invite.",
                }
            )
        )
    gid = _uuid_from_any(char["guild_id"])
    g = await db.fetchrow("SELECT * FROM guilds WHERE id=$1", gid)
    if not g:
        # Character still pointed at a deleted guild — clear so Activity join/create works.
        await db.execute(
            "UPDATE characters SET guild_id=NULL, guild_rank=NULL WHERE id=$1",
            _uuid_from_any(char["id"]),
        )
        return web.json_response(
            _json_safe(
                {
                    "ok": True,
                    "in_guild": False,
                    "message": "Your previous guild no longer exists. Create a hall here or accept a new invite.",
                }
            )
        )
    member_count = await db.fetchval(
        "SELECT COUNT(*)::int FROM characters WHERE guild_id=$1",
        gid,
    )
    from services.guild import guild_boss as guild_boss_mod
    from services.guild import guild_tech as guild_tech_mod
    from services.guild import guild_checkin as guild_checkin_mod
    from services.guild import guild_raid as guild_raid_mod

    bot = request.app.get("bot")
    enc = await guild_boss_mod.active_encounter_for_guild(db, gid)
    if enc:
        enc = await guild_boss_mod.refresh_encounter_if_expired(db, enc, bot)
    boss_payload = None
    if enc:
        boss_payload = {
            "encounter": _json_safe(dict(enc)),
            "template": guild_boss_mod.BOSS_TEMPLATES.get(enc.get("boss_key"), {}),
            "leaderboard": _json_safe(await guild_boss_mod.leaderboard(db, UUID(str(enc["id"]))))
            if enc.get("status") == "active"
            else [],
        }
    unlocked = await guild_tech_mod.fetch_unlocked_ids(db, gid)
    tech_funds = await guild_tech_mod.tech_progress_payload(db, gid)
    char_svc = CharacterService(db)
    char_id = _uuid_from_any(char["id"])
    raids = await guild_raid_mod.list_runs(db, gid, limit=8)
    raid_templates = await guild_raid_mod.unlocked_raid_templates(db, gid)
    active_row = await db.fetchrow(
        """
        SELECT * FROM guild_raid_runs
        WHERE guild_id = $1 AND status IN ('recruiting', 'active')
        ORDER BY created_at DESC
        LIMIT 1
        """,
        gid,
    )
    active_raid = None
    if active_row:
        active_raid = await guild_raid_mod.run_state_payload(db, UUID(str(active_row["id"])), char_id, char_svc)
    checkin = await guild_checkin_mod.status_payload(db, gid, char_id)
    from services.guild import guild_quests as guild_quests_mod

    quests = await guild_quests_mod.list_for_guild(db, gid, char_id)
    return web.json_response(
        _json_safe(
            {
                "ok": True,
                "in_guild": True,
                "guild": {
                    **dict(g),
                    "member_count": int(member_count or 0),
                    "my_rank": char.get("guild_rank"),
                    "my_character_id": str(char["id"]),
                },
                "boss": boss_payload,
                "tech": {
                    "definitions": guild_tech_mod.tech_definitions_payload(),
                    "unlocked": unlocked,
                    "funds": tech_funds.get("funds") or {},
                },
                "raids": {
                    "recent": raids,
                    "templates_available": raid_templates,
                    "active": active_raid,
                },
                "checkin": checkin,
                "quests": quests,
            }
        )
    )


async def handle_guild_quest_claim(request: web.Request) -> web.Response:
    try:
        _user, _discord_id, char, db = await _authed_discord_user_and_char(request)
    except web.HTTPException:
        raise
    if not char or not char.get("guild_id"):
        return web.json_response(_json_safe({"ok": False, "error": "not_in_guild"}), status=400)
    try:
        body = await request.json()
    except (json.JSONDecodeError, ValueError, TypeError):
        body = {}
    if not isinstance(body, dict):
        body = {}
    quest_key = str(body.get("quest_key") or "").strip()
    if not quest_key:
        return web.json_response(_json_safe({"ok": False, "message": "quest_key required"}), status=400)
    from services.guild import guild_quests as guild_quests_mod

    char_svc = CharacterService(db)
    gid = _uuid_from_any(char["guild_id"])
    char_id = _uuid_from_any(char["id"])
    ok, msg, delivery, quests = await guild_quests_mod.claim(db, char_svc, gid, char_id, quest_key)
    status = 200 if ok else 400
    return web.json_response(
        _json_safe({"ok": ok, "message": msg, "delivery": delivery, "quests": quests}),
        status=status,
    )


async def handle_battle_pass_unlock_premium(request: web.Request) -> web.Response:
    try:
        _user, _discord_id, char, db = await _authed_discord_user_and_char(request)
    except web.HTTPException:
        raise
    if not char:
        return web.json_response(_json_safe({"ok": False, "error": "no_character"}), status=400)
    from services.battle_pass.battle_pass_service import BattlePassService

    bp = BattlePassService(db)
    ok, msg = await bp.unlock_premium(_uuid_from_any(char["id"]))
    state = await bp.get_state(_uuid_from_any(char["id"]))
    return web.json_response(_json_safe({"ok": ok, "message": msg, "battle_pass": state}), status=200 if ok else 400)


async def handle_guild_checkin_post(request: web.Request) -> web.Response:
    """POST — daily guild hall check-in (UTC calendar day)."""
    try:
        _user, discord_id, char, db = await _authed_discord_user_and_char(request)
    except web.HTTPException:
        raise
    if not char or not char.get("guild_id"):
        return web.json_response(_json_safe({"ok": False, "error": "not_in_guild", "message": "Not in a guild."}), status=400)
    gid = _uuid_from_any(char["guild_id"])
    g = await db.fetchrow("SELECT id FROM guilds WHERE id=$1", gid)
    if not g:
        return web.json_response(_json_safe({"ok": False, "error": "guild_missing", "message": "Guild not found."}), status=400)
    from services.guild import guild_checkin as guild_checkin_mod

    char_svc = CharacterService(db)
    char_id = _uuid_from_any(char["id"])
    ok, msg, st = await guild_checkin_mod.perform_checkin(db, char_svc, gid, char_id)
    if ok:
        from services.battle_pass.battle_pass_service import BattlePassService
        from services.battle_pass.battle_pass_service import XP_GUILD_CHECKIN

        bp = BattlePassService(db)
        today = guild_checkin_mod.utc_today().isoformat()
        await bp.try_grant_xp(char_id, f"guild_checkin_{gid}_{today}", XP_GUILD_CHECKIN, "guild_checkin")
    return web.json_response(_json_safe({"ok": ok, "message": msg, "checkin": st}))


async def handle_guild_bank_deposit(request: web.Request) -> web.Response:
    try:
        _user, discord_id, char, db = await _authed_discord_user_and_char(request)
    except web.HTTPException:
        raise
    if not char or not char.get("guild_id"):
        return web.json_response(_json_safe({"ok": False, "error": "not_in_guild"}), status=400)
    try:
        body = await request.json()
    except (json.JSONDecodeError, ValueError, TypeError):
        body = {}
    if not isinstance(body, dict):
        body = {}
    amount = int(body.get("amount") or 0)
    from services.guild.guild_bank import deposit

    char_svc = CharacterService(db)
    gid = _uuid_from_any(char["guild_id"])
    ok, msg = await deposit(db, char_svc, gid, _uuid_from_any(char["id"]), amount)
    if not ok:
        return web.json_response(_json_safe({"ok": False, "message": msg}), status=400)
    from services.guild.guild_feed import post_system

    await post_system(
        db,
        gid,
        f"**{char['name']}** donated **{amount:,}** gold to the guild bank.",
        "system_bank",
        {"amount": amount},
    )
    bot = request.app.get("bot")
    if bot:
        try:
            from services.guild.guild_discord_announce import post_to_guild_announce_channel

            await post_to_guild_announce_channel(
                bot,
                db,
                gid,
                text=f"💰 **{char['name']}** donated **{amount:,}** gold to the guild bank.",
            )
        except Exception as e:
            log.warning("guild bank deposit Discord announce: %s", e)
    g2 = await db.fetchrow("SELECT bank_gold FROM guilds WHERE id=$1", gid)
    return web.json_response(_json_safe({"ok": True, "bank_gold": int(g2["bank_gold"] or 0) if g2 else 0}))


async def handle_guild_bank_withdraw(request: web.Request) -> web.Response:
    try:
        _user, discord_id, char, db = await _authed_discord_user_and_char(request)
    except web.HTTPException:
        raise
    if not char or not char.get("guild_id"):
        return web.json_response(_json_safe({"ok": False, "error": "not_in_guild"}), status=400)
    try:
        body = await request.json()
    except (json.JSONDecodeError, ValueError, TypeError):
        body = {}
    if not isinstance(body, dict):
        body = {}
    amount = int(body.get("amount") or 0)
    from services.guild.guild_bank import withdraw

    char_svc = CharacterService(db)
    gid = _uuid_from_any(char["guild_id"])
    ok, msg = await withdraw(
        db,
        char_svc,
        gid,
        _uuid_from_any(char["id"]),
        char.get("guild_rank"),
        amount,
    )
    if not ok:
        return web.json_response(_json_safe({"ok": False, "message": msg}), status=400)
    from services.guild.guild_feed import post_system

    await post_system(
        db,
        gid,
        f"**{char['name']}** (officer) withdrew **{amount:,}** gold from the guild bank.",
        "system_bank",
        {"amount": amount},
    )
    bot = request.app.get("bot")
    if bot:
        try:
            from services.guild.guild_discord_announce import post_to_guild_announce_channel

            await post_to_guild_announce_channel(
                bot,
                db,
                gid,
                text=f"🏧 **{char['name']}** (officer) withdrew **{amount:,}** gold from the guild bank.",
            )
        except Exception as e:
            log.warning("guild bank withdraw Discord announce: %s", e)
    g2 = await db.fetchrow("SELECT bank_gold FROM guilds WHERE id=$1", gid)
    fresh = await char_svc.get_character(discord_id)
    return web.json_response(
        _json_safe(
            {
                "ok": True,
                "bank_gold": int(g2["bank_gold"] or 0) if g2 else 0,
                "character_gold": int(fresh["gold"]) if fresh else None,
            }
        )
    )


async def handle_guild_feed_get(request: web.Request) -> web.Response:
    try:
        _user, discord_id, char, db = await _authed_discord_user_and_char(request)
    except web.HTTPException:
        raise
    if not char or not char.get("guild_id"):
        return web.json_response(_json_safe({"ok": False, "error": "not_in_guild"}), status=400)
    cursor = request.rel_url.query.get("cursor") or ""
    before_id = None
    if cursor:
        try:
            before_id = UUID(cursor)
        except (ValueError, TypeError):
            pass
    from services.guild.guild_feed import fetch_feed

    gid = _uuid_from_any(char["guild_id"])
    rows = await fetch_feed(db, gid, before_id=before_id)
    next_cursor = str(rows[-1]["id"]) if rows else None
    return web.json_response(_json_safe({"ok": True, "messages": rows, "next_cursor": next_cursor}))


async def handle_guild_feed_post(request: web.Request) -> web.Response:
    try:
        _user, discord_id, char, db = await _authed_discord_user_and_char(request)
    except web.HTTPException:
        raise
    if not char or not char.get("guild_id"):
        return web.json_response(_json_safe({"ok": False, "error": "not_in_guild"}), status=400)
    try:
        body = await request.json()
    except (json.JSONDecodeError, ValueError, TypeError):
        body = {}
    if not isinstance(body, dict):
        body = {}
    text = str(body.get("body") or "")
    nrecent = await db.fetchval(
        """
        SELECT COUNT(*)::int FROM guild_feed_messages
        WHERE guild_id = $1 AND author_character_id = $2
          AND created_at > NOW() - INTERVAL '45 seconds'
        """,
        _uuid_from_any(char["guild_id"]),
        _uuid_from_any(char["id"]),
    )
    if int(nrecent or 0) >= 6:
        return web.json_response(_json_safe({"ok": False, "message": "Slow down — too many messages."}), status=429)
    from services.guild.guild_feed import post_chat

    gid = _uuid_from_any(char["guild_id"])
    ok, msg = await post_chat(db, gid, _uuid_from_any(char["id"]), text)
    if not ok:
        return web.json_response(_json_safe({"ok": False, "message": msg}), status=400)
    return web.json_response(_json_safe({"ok": True}))


async def handle_guild_boss_start(request: web.Request) -> web.Response:
    try:
        _user, discord_id, char, db = await _authed_discord_user_and_char(request)
    except web.HTTPException:
        raise
    if not char or not char.get("guild_id"):
        return web.json_response(_json_safe({"ok": False, "error": "not_in_guild"}), status=400)
    try:
        body = await request.json()
    except (json.JSONDecodeError, ValueError, TypeError):
        body = {}
    if not isinstance(body, dict):
        body = {}
    boss_key = str(body.get("boss_key") or "stone_siege_golem").strip()
    from services.guild import guild_boss as guild_boss_mod

    gid = _uuid_from_any(char["guild_id"])
    bot = request.app.get("bot")
    enc, err = await guild_boss_mod.start_encounter(db, gid, boss_key, char.get("guild_rank"), discord_bot=bot)
    if err:
        return web.json_response(_json_safe({"ok": False, "message": err}), status=400)
    tpl = guild_boss_mod.BOSS_TEMPLATES.get(boss_key, {})
    try:
        from services.guild.guild_feed import post_system

        await post_system(
            db,
            gid,
            f"A guild boss has appeared: **{tpl.get('name', boss_key)}**! Strike together before time runs out.",
            "system_boss",
            {"boss_key": boss_key},
        )
    except Exception as e:
        log.warning("guild boss spawn feed post failed: %s", e)
    if bot and enc:
        try:
            import discord

            from services.guild.guild_discord_announce import post_to_guild_announce_channel

            hp = int(enc.get("hp_max") or tpl.get("hp_max") or 0)
            lines = [f"**{tpl.get('name', boss_key)}**", f"**HP:** {hp:,}"]
            closes = enc.get("closes_at")
            if closes:
                try:
                    lines.append(f"**Ends:** <t:{int(closes.timestamp())}:R>")
                except Exception:
                    pass
            lines.append("_Open the Activity **Guild** tab to strike._")
            emb = discord.Embed(
                title="Guild boss summoned",
                description="\n".join(lines),
                color=0xC9A227,
            )
            await post_to_guild_announce_channel(bot, db, gid, embed=emb)
        except Exception as log_ex:
            log.warning("guild boss spawn Discord announce: %s", log_ex)

    return web.json_response(_json_safe({"ok": True, "encounter": dict(enc) if enc else None}))


async def handle_guild_boss_hit(request: web.Request) -> web.Response:
    try:
        _user, discord_id, char, db = await _authed_discord_user_and_char(request)
    except web.HTTPException:
        raise
    if not char or not char.get("guild_id"):
        return web.json_response(_json_safe({"ok": False, "error": "not_in_guild"}), status=400)
    try:
        body = await request.json()
    except (json.JSONDecodeError, ValueError, TypeError):
        body = {}
    if not isinstance(body, dict):
        body = {}
    eid_raw = body.get("encounter_id")
    from services.guild import guild_boss as guild_boss_mod

    gid = _uuid_from_any(char["guild_id"])
    bot = request.app.get("bot")
    if eid_raw:
        try:
            eid = UUID(str(eid_raw))
        except (ValueError, TypeError):
            return web.json_response(_json_safe({"ok": False, "message": "Bad encounter_id."}), status=400)
    else:
        enc = await guild_boss_mod.active_encounter_for_guild(db, gid)
        if not enc:
            return web.json_response(_json_safe({"ok": False, "message": "No active boss."}), status=400)
        enc = await guild_boss_mod.refresh_encounter_if_expired(db, enc, bot)
        if enc.get("status") != "active":
            return web.json_response(_json_safe({"ok": False, "message": "No active boss."}), status=400)
        eid = UUID(str(enc["id"]))

    char_svc = CharacterService(db)
    ok, msg, enc2 = await guild_boss_mod.apply_hit(db, char_svc, char, eid, discord_bot=bot)
    if not ok:
        st = 429 if "Wait" in msg else 400
        return web.json_response(_json_safe({"ok": False, "message": msg}), status=st)
    lb = await guild_boss_mod.leaderboard(db, eid)
    return web.json_response(_json_safe({"ok": True, "message": msg, "encounter": enc2, "leaderboard": lb}))


async def handle_guild_tech_unlock(request: web.Request) -> web.Response:
    try:
        _user, discord_id, char, db = await _authed_discord_user_and_char(request)
    except web.HTTPException:
        raise
    if not char or not char.get("guild_id"):
        return web.json_response(_json_safe({"ok": False, "error": "not_in_guild"}), status=400)
    try:
        body = await request.json()
    except (json.JSONDecodeError, ValueError, TypeError):
        body = {}
    if not isinstance(body, dict):
        body = {}
    node_id = str(body.get("node_id") or "").strip()
    from services.guild import guild_tech as guild_tech_mod

    gid = _uuid_from_any(char["guild_id"])
    ok, msg = await guild_tech_mod.unlock_node(
        db,
        gid,
        node_id,
        _uuid_from_any(char["id"]),
        char.get("guild_rank"),
    )
    if not ok:
        return web.json_response(_json_safe({"ok": False, "message": msg}), status=400)
    from services.guild.guild_feed import post_system

    name = guild_tech_mod.TECH_NODES.get(node_id, {}).get("name", node_id)
    await post_system(db, gid, f"Guild unlocked tech: **{name}**.", "system", {"node_id": node_id})
    bot = request.app.get("bot")
    if bot:
        try:
            import discord

            from services.guild.guild_discord_announce import post_to_guild_announce_channel

            desc = guild_tech_mod.TECH_NODES.get(node_id, {}).get("description", "")
            emb = discord.Embed(
                title="Guild tech unlocked",
                description=f"**{name}**\n{desc}"[:4096],
                color=0x3498DB,
            )
            await post_to_guild_announce_channel(bot, db, gid, embed=emb)
        except Exception as e:
            log.warning("guild tech Discord announce: %s", e)
    g2 = await db.fetchrow("SELECT guild_xp, bank_gold FROM guilds WHERE id=$1", gid)
    unlocked = await guild_tech_mod.fetch_unlocked_ids(db, gid)
    return web.json_response(
        _json_safe(
            {
                "ok": True,
                "guild_xp": int(g2["guild_xp"] or 0) if g2 else 0,
                "bank_gold": int(g2["bank_gold"] or 0) if g2 else 0,
                "unlocked": unlocked,
            }
        )
    )


async def handle_guild_raid_create(request: web.Request) -> web.Response:
    try:
        _user, discord_id, char, db = await _authed_discord_user_and_char(request)
    except web.HTTPException:
        raise
    if not char or not char.get("guild_id"):
        return web.json_response(_json_safe({"ok": False, "error": "not_in_guild"}), status=400)
    try:
        body = await request.json()
    except (json.JSONDecodeError, ValueError, TypeError):
        body = {}
    if not isinstance(body, dict):
        body = {}
    template_key = str(body.get("template_key") or "gnoll_warren_raid").strip()
    from services.guild import guild_raid as guild_raid_mod

    gid = _uuid_from_any(char["guild_id"])
    run, err = await guild_raid_mod.create_run(db, gid, template_key, _uuid_from_any(char["id"]), char.get("guild_rank"))
    if err:
        return web.json_response(_json_safe({"ok": False, "message": err}), status=400)
    parts = await guild_raid_mod.participants_for_run(db, UUID(str(run["id"])))
    bot = request.app.get("bot")
    if bot and run:
        try:
            import discord

            from services.guild.guild_discord_announce import post_to_guild_announce_channel

            tpl = guild_raid_mod.RAID_TEMPLATES.get(template_key, {})
            emb = discord.Embed(
                title="Guild raid scheduled",
                description=f"**{tpl.get('name', template_key)}**\n_Sign up in the Activity **Guild** tab._",
                color=0x8E44AD,
            )
            await post_to_guild_announce_channel(bot, db, gid, embed=emb)
        except Exception as e:
            log.warning("guild raid create Discord announce: %s", e)
    return web.json_response(_json_safe({"ok": True, "run": dict(run), "participants": parts}))


async def handle_guild_raid_signup(request: web.Request) -> web.Response:
    try:
        _user, discord_id, char, db = await _authed_discord_user_and_char(request)
    except web.HTTPException:
        raise
    if not char or not char.get("guild_id"):
        return web.json_response(_json_safe({"ok": False, "error": "not_in_guild"}), status=400)
    try:
        body = await request.json()
    except (json.JSONDecodeError, ValueError, TypeError):
        body = {}
    if not isinstance(body, dict):
        body = {}
    from services.guild import guild_raid as guild_raid_mod

    gid = _uuid_from_any(char["guild_id"])
    try:
        run_id = UUID(str(body.get("run_id") or ""))
    except (ValueError, TypeError):
        return web.json_response(_json_safe({"ok": False, "message": "Missing or invalid run_id."}), status=400)
    ok, msg = await guild_raid_mod.signup(db, run_id, _uuid_from_any(char["id"]), gid)
    if not ok:
        return web.json_response(_json_safe({"ok": False, "message": msg}), status=400)
    parts = await guild_raid_mod.participants_for_run(db, run_id)
    return web.json_response(_json_safe({"ok": True, "participants": parts}))


async def handle_guild_raid_start(request: web.Request) -> web.Response:
    try:
        _user, discord_id, char, db = await _authed_discord_user_and_char(request)
    except web.HTTPException:
        raise
    if not char or not char.get("guild_id"):
        return web.json_response(_json_safe({"ok": False, "error": "not_in_guild"}), status=400)
    try:
        body = await request.json()
    except (json.JSONDecodeError, ValueError, TypeError):
        body = {}
    if not isinstance(body, dict):
        body = {}
    from services.guild import guild_raid as guild_raid_mod

    try:
        run_id = UUID(str(body.get("run_id") or ""))
    except (ValueError, TypeError):
        return web.json_response(_json_safe({"ok": False, "message": "Missing or invalid run_id."}), status=400)
    ok, msg = await guild_raid_mod.start_run(db, run_id, _uuid_from_any(char["id"]), char.get("guild_rank"))
    if not ok:
        return web.json_response(_json_safe({"ok": False, "message": msg}), status=400)
    run = await db.fetchrow("SELECT * FROM guild_raid_runs WHERE id=$1", run_id)
    return web.json_response(_json_safe({"ok": True, "run": dict(run) if run else None}))


async def handle_guild_tech_contribute(request: web.Request) -> web.Response:
    try:
        _user, discord_id, char, db = await _authed_discord_user_and_char(request)
    except web.HTTPException:
        raise
    if not char or not char.get("guild_id"):
        return web.json_response(_json_safe({"ok": False, "error": "not_in_guild"}), status=400)
    try:
        body = await request.json()
    except (json.JSONDecodeError, ValueError, TypeError):
        body = {}
    if not isinstance(body, dict):
        body = {}
    node_id = str(body.get("node_id") or "").strip()
    amount = int(body.get("amount") or 0)
    from services.guild import guild_tech as guild_tech_mod

    gid = _uuid_from_any(char["guild_id"])
    char_svc = CharacterService(db)
    ok, msg, progress = await guild_tech_mod.contribute(
        db, char_svc, gid, node_id, _uuid_from_any(char["id"]), amount
    )
    if not ok:
        return web.json_response(_json_safe({"ok": False, "message": msg}), status=400)
    funds = await guild_tech_mod.tech_progress_payload(db, gid)
    fresh = await char_svc.get_character(discord_id)
    return web.json_response(
        _json_safe(
            {
                "ok": True,
                "message": msg,
                "progress": progress,
                "funds": funds.get("funds") or {},
                "gold": int(fresh.get("gold") or 0) if fresh else None,
            }
        )
    )


async def handle_guild_tech_finalize(request: web.Request) -> web.Response:
    try:
        _user, discord_id, char, db = await _authed_discord_user_and_char(request)
    except web.HTTPException:
        raise
    if not char or not char.get("guild_id"):
        return web.json_response(_json_safe({"ok": False, "error": "not_in_guild"}), status=400)
    try:
        body = await request.json()
    except (json.JSONDecodeError, ValueError, TypeError):
        body = {}
    if not isinstance(body, dict):
        body = {}
    node_id = str(body.get("node_id") or "").strip()
    from services.guild import guild_tech as guild_tech_mod

    gid = _uuid_from_any(char["guild_id"])
    ok, msg = await guild_tech_mod.finalize_research(
        db, gid, node_id, _uuid_from_any(char["id"]), char.get("guild_rank")
    )
    if not ok:
        return web.json_response(_json_safe({"ok": False, "message": msg}), status=400)
    from services.guild.guild_feed import post_system

    name = guild_tech_mod.TECH_NODES.get(node_id, {}).get("name", node_id)
    await post_system(db, gid, f"Guild finalized research: **{name}**.", "system", {"node_id": node_id})
    g2 = await db.fetchrow("SELECT guild_xp, bank_gold FROM guilds WHERE id=$1", gid)
    unlocked = await guild_tech_mod.fetch_unlocked_ids(db, gid)
    funds = await guild_tech_mod.tech_progress_payload(db, gid)
    return web.json_response(
        _json_safe(
            {
                "ok": True,
                "guild_xp": int(g2["guild_xp"] or 0) if g2 else 0,
                "bank_gold": int(g2["bank_gold"] or 0) if g2 else 0,
                "unlocked": unlocked,
                "funds": funds.get("funds") or {},
            }
        )
    )


async def handle_guild_raid_strike(request: web.Request) -> web.Response:
    try:
        _user, discord_id, char, db = await _authed_discord_user_and_char(request)
    except web.HTTPException:
        raise
    if not char or not char.get("guild_id"):
        return web.json_response(_json_safe({"ok": False, "error": "not_in_guild"}), status=400)
    try:
        body = await request.json()
    except (json.JSONDecodeError, ValueError, TypeError):
        body = {}
    if not isinstance(body, dict):
        body = {}
    try:
        run_id = UUID(str(body.get("run_id") or ""))
    except (ValueError, TypeError):
        return web.json_response(_json_safe({"ok": False, "message": "Missing or invalid run_id."}), status=400)
    from services.guild import guild_raid as guild_raid_mod

    char_svc = CharacterService(db)
    bot = request.app.get("bot")
    ok, msg, run, rewards = await guild_raid_mod.strike(db, char_svc, run_id, char, discord_bot=bot)
    if not ok:
        return web.json_response(_json_safe({"ok": False, "message": msg}), status=400)
    state = await guild_raid_mod.run_state_payload(db, run_id, _uuid_from_any(char["id"]), char_svc)
    return web.json_response(
        _json_safe({"ok": True, "message": msg, "run": run, "state": state, "rewards": rewards})
    )


async def handle_guild_raid_state(request: web.Request) -> web.Response:
    try:
        _user, discord_id, char, db = await _authed_discord_user_and_char(request)
    except web.HTTPException:
        raise
    if not char or not char.get("guild_id"):
        return web.json_response(_json_safe({"ok": False, "error": "not_in_guild"}), status=400)
    run_id_raw = request.query.get("run_id") or ""
    try:
        run_id = UUID(str(run_id_raw))
    except (ValueError, TypeError):
        return web.json_response(_json_safe({"ok": False, "message": "Missing or invalid run_id."}), status=400)
    from services.guild import guild_raid as guild_raid_mod

    char_svc = CharacterService(db)
    state = await guild_raid_mod.run_state_payload(db, run_id, _uuid_from_any(char["id"]), char_svc)
    if not state:
        return web.json_response(_json_safe({"ok": False, "message": "Raid not found."}), status=404)
    return web.json_response(_json_safe({"ok": True, "state": state}))


async def handle_guild_raid_bonus_start(request: web.Request) -> web.Response:
    try:
        _user, discord_id, char, db = await _authed_discord_user_and_char(request)
    except web.HTTPException:
        raise
    if not char or not char.get("guild_id"):
        return web.json_response(_json_safe({"ok": False, "error": "not_in_guild"}), status=400)
    try:
        body = await request.json()
    except (json.JSONDecodeError, ValueError, TypeError):
        body = {}
    if not isinstance(body, dict):
        body = {}
    try:
        run_id = UUID(str(body.get("run_id") or ""))
    except (ValueError, TypeError):
        return web.json_response(_json_safe({"ok": False, "message": "Missing or invalid run_id."}), status=400)
    from services.guild import guild_raid as guild_raid_mod
    from services.combat import activity_combat as activity_combat_api

    gid = _uuid_from_any(char["guild_id"])
    ok, msg, meta = await guild_raid_mod.start_bonus_combat(db, run_id, _uuid_from_any(char["id"]), gid)
    if not ok:
        return web.json_response(_json_safe({"ok": False, "message": msg}), status=400)
    enemy_key = str((meta or {}).get("enemy_key") or "gnoll_raider")
    discord_guild_id = _guild_id_from_request(request, body)
    char_svc = CharacterService(db)
    if discord_guild_id and char:
        await char_svc.set_last_discord_guild(char["id"], discord_guild_id)
    result = await activity_combat_api.start_activity_combat(
        request.app["bot"],
        discord_id,
        discord_guild_id,
        force=bool(body.get("force")),
        enemy_key=enemy_key,
        guild_raid_run_id=run_id,
    )
    status = 200
    if result.get("error") == "already_in_combat":
        status = 409
    elif result.get("error"):
        status = 400
    return web.json_response(_json_safe({**result, "raid_meta": meta}), status=status)


async def handle_guild_raid_cancel(request: web.Request) -> web.Response:
    try:
        _user, discord_id, char, db = await _authed_discord_user_and_char(request)
    except web.HTTPException:
        raise
    if not char or not char.get("guild_id"):
        return web.json_response(_json_safe({"ok": False, "error": "not_in_guild"}), status=400)
    try:
        body = await request.json()
    except (json.JSONDecodeError, ValueError, TypeError):
        body = {}
    if not isinstance(body, dict):
        body = {}
    try:
        run_id = UUID(str(body.get("run_id") or ""))
    except (ValueError, TypeError):
        return web.json_response(_json_safe({"ok": False, "message": "Missing or invalid run_id."}), status=400)
    from services.guild import guild_raid as guild_raid_mod

    ok, msg = await guild_raid_mod.cancel_run(db, run_id, char.get("guild_rank"))
    if not ok:
        return web.json_response(_json_safe({"ok": False, "message": msg}), status=400)
    run = await db.fetchrow("SELECT * FROM guild_raid_runs WHERE id=$1", run_id)
    return web.json_response(_json_safe({"ok": True, "message": msg, "run": dict(run) if run else None}))


async def handle_guild_raid_complete(request: web.Request) -> web.Response:
    try:
        _user, discord_id, char, db = await _authed_discord_user_and_char(request)
    except web.HTTPException:
        raise
    if not char or not char.get("guild_id"):
        return web.json_response(_json_safe({"ok": False, "error": "not_in_guild"}), status=400)
    try:
        body = await request.json()
    except (json.JSONDecodeError, ValueError, TypeError):
        body = {}
    if not isinstance(body, dict):
        body = {}
    from services.guild import guild_raid as guild_raid_mod

    try:
        run_id = UUID(str(body.get("run_id") or ""))
    except (ValueError, TypeError):
        return web.json_response(_json_safe({"ok": False, "message": "Missing or invalid run_id."}), status=400)
    char_svc = CharacterService(db)
    bot = request.app.get("bot")
    ok, msg, rewards = await guild_raid_mod.complete_run(
        db,
        char_svc,
        run_id,
        _uuid_from_any(char["id"]),
        char.get("guild_rank"),
        discord_bot=bot,
    )
    if not ok:
        return web.json_response(_json_safe({"ok": False, "message": msg}), status=400)
    run = await db.fetchrow("SELECT * FROM guild_raid_runs WHERE id=$1", run_id)
    return web.json_response(_json_safe({"ok": True, "run": dict(run) if run else None, "rewards": rewards}))


async def handle_guild_invite_candidates(request: web.Request) -> web.Response:
    """Search guildless characters by name prefix for Activity invite UI (officers only)."""
    try:
        _user, discord_id, char, db = await _authed_discord_user_and_char(request)
    except web.HTTPException:
        raise
    if not char or not char.get("guild_id"):
        return web.json_response(_json_safe({"ok": False, "error": "not_in_guild", "players": []}), status=400)
    rnk = (char.get("guild_rank") or "").lower()
    if rnk not in ("guildmaster", "officer"):
        return web.json_response(_json_safe({"ok": False, "error": "forbidden", "players": []}), status=403)

    q = str((request.query.get("q") or "")).strip()
    if not q:
        return web.json_response(_json_safe({"ok": True, "players": []}))
    q = q[:32]
    inviter_player_id = char["player_id"]
    q_esc = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"

    rows = await db.fetch(
        """
        SELECT c.id, c.name, c.level, c.class, c.player_id, p.username
        FROM characters c
        JOIN players p ON p.id = c.player_id
        WHERE c.is_active = TRUE
          AND c.guild_id IS NULL
          AND c.player_id != $1
          AND c.name ILIKE $2 ESCAPE '\\'
        ORDER BY c.name ASC
        LIMIT 15
        """,
        inviter_player_id,
        q_esc,
    )
    players = [
        {
            "character_id": str(r["id"]),
            "name": r["name"],
            "level": int(r["level"] or 1),
            "class": r["class"],
            "username": str(r["username"]) if r.get("username") is not None else None,
        }
        for r in rows
    ]
    return web.json_response(_json_safe({"ok": True, "players": players}))


async def handle_guild_invite_send(request: web.Request) -> web.Response:
    """Officer sends the same Discord DM invite flow as `/guild invite`."""
    bot = request.app.get("bot")
    try:
        _user, discord_id, char, db = await _authed_discord_user_and_char(request)
    except web.HTTPException:
        raise
    if not char or not char.get("guild_id"):
        return web.json_response(_json_safe({"ok": False, "message": "You're not in a guild."}), status=400)
    rnk = (char.get("guild_rank") or "").lower()
    if rnk not in ("guildmaster", "officer"):
        return web.json_response(_json_safe({"ok": False, "message": "Only guildmasters and officers can invite."}), status=403)
    if not bot:
        return web.json_response(
            _json_safe({"ok": False, "message": "Bot is unavailable — try again from Discord."}),
            status=503,
        )

    try:
        body = await request.json()
    except (json.JSONDecodeError, ValueError, TypeError):
        body = {}
    if not isinstance(body, dict):
        body = {}
    raw_tid = body.get("target_character_id") or body.get("character_id")
    if not raw_tid:
        return web.json_response(_json_safe({"ok": False, "message": "Missing target_character_id."}), status=400)
    try:
        target_cid = _uuid_from_any(raw_tid)
    except (ValueError, TypeError):
        return web.json_response(_json_safe({"ok": False, "message": "Invalid character id."}), status=400)

    gid = _uuid_from_any(char["guild_id"])
    guild = await db.fetchrow("SELECT * FROM guilds WHERE id=$1", gid)
    if not guild:
        return web.json_response(_json_safe({"ok": False, "message": "Guild not found."}), status=400)
    if int(guild["member_count"] or 0) >= int(guild["max_members"] or 0):
        return web.json_response(_json_safe({"ok": False, "message": "Guild is full."}), status=400)

    target = await db.fetchrow(
        """
        SELECT c.id, c.name, c.guild_id, c.player_id, c.is_active
        FROM characters c
        WHERE c.id = $1
        """,
        target_cid,
    )
    if not target:
        return web.json_response(_json_safe({"ok": False, "message": "Character not found."}), status=400)
    if not target.get("is_active"):
        return web.json_response(_json_safe({"ok": False, "message": "That character is inactive."}), status=400)
    if target["guild_id"]:
        return web.json_response(_json_safe({"ok": False, "message": "That player is already in a guild."}), status=400)
    if int(target["player_id"]) == int(char["player_id"]):
        return web.json_response(_json_safe({"ok": False, "message": "You can't invite your own account."}), status=400)

    from services.guild import guild_invites as guild_invites_mod
    from services.guild.guild_invite_dm import GuildInviteView, build_guild_invite_embed

    char_svc = CharacterService(db)
    target_discord_id = int(target["player_id"])
    await guild_invites_mod.upsert_pending_invite(
        db,
        gid,
        target_discord_id,
        inviter_character_id=_uuid_from_any(char["id"]),
    )
    embed = build_guild_invite_embed(dict(guild), char["name"])
    view = GuildInviteView(guild["id"], bot, char_svc)
    try:
        user = await bot.fetch_user(target_discord_id)
        await user.send(embed=embed, view=view)
    except discord.Forbidden:
        return web.json_response(
            _json_safe(
                {
                    "ok": False,
                    "message": "Could not DM that player — they may have DMs disabled.",
                }
            ),
            status=400,
        )
    except discord.HTTPException as e:
        log.warning("guild invite DM HTTP error: %s", e)
        return web.json_response(
            _json_safe({"ok": False, "message": "Discord could not deliver the invite. Try again later."}),
            status=502,
        )

    return web.json_response(
        _json_safe({"ok": True, "message": f"Invited {target['name']} — they received a DM with Accept / Decline."})
    )


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
    # Game accounts don't need Discord, so the API must not either. It used to
    # refuse to start without DISCORD_CLIENT_SECRET, which made "players don't
    # depend on Discord" false at the server level. Start if EITHER auth path is
    # configured; the Discord routes still self-check and 503 when their secret
    # is missing (see handle_token / handle_auth_discord_exchange).
    _has_discord = bool((os.getenv("DISCORD_CLIENT_SECRET") or "").strip())
    _has_native = bool((os.getenv("SESSION_JWT_SECRET") or "").strip())
    if not _has_discord and not _has_native:
        log.info(
            "Neither DISCORD_CLIENT_SECRET nor SESSION_JWT_SECRET is set — HTTP API disabled. "
            "Set DISCORD_CLIENT_SECRET for Discord login, SESSION_JWT_SECRET for game accounts."
        )
        return None

    app = web.Application(middlewares=[cors_middleware, rate_limit_middleware])
    app["bot"] = bot

    app.router.add_post("/api/token", handle_token)
    app.router.add_post("/api/auth/discord/exchange", handle_auth_discord_exchange)
    app.router.add_get("/auth/mobile-callback", handle_auth_mobile_callback)
    # Game accounts — no Discord required. Throttled by IP in
    # rate_limit_middleware (fail-closed) plus a per-account bucket inside the
    # login/forgot handlers.
    app.router.add_post("/api/auth/native/signup", handle_auth_native_signup)
    app.router.add_post("/api/auth/native/login", handle_auth_native_login)
    app.router.add_post("/api/auth/password/forgot", handle_auth_password_forgot)
    app.router.add_post("/api/auth/password/reset", handle_auth_password_reset)
    app.router.add_post("/api/auth/email/verify", handle_auth_email_verify)
    # Linking is session-authenticated (not credential-checking), but still
    # rides the /api/auth/* IP throttle above.
    app.router.add_get("/api/auth/link/status", handle_auth_link_status)
    app.router.add_post("/api/auth/link/discord", handle_auth_link_discord)
    app.router.add_post("/api/auth/link/resolve", handle_auth_link_resolve)
    app.router.add_get("/api/game/inventory", handle_inventory)
    app.router.add_get("/api/game/character/stats", handle_character_stats)
    app.router.add_get("/api/game/character/class-options", handle_character_class_options)
    app.router.add_post("/api/game/character/create", handle_character_create)
    app.router.add_get("/api/game/equipment", handle_equipment)
    app.router.add_get("/api/game/progress", handle_progress)
    app.router.add_get("/api/game/specializations", handle_specializations)
    app.router.add_post("/api/game/character/specialization", handle_specialization_choose)
    app.router.add_get("/api/game/map", handle_map)
    app.router.add_get("/api/game/quests", handle_quests)
    app.router.add_get("/api/game/deeds", handle_deeds)
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
    app.router.add_post("/api/game/item/salvage", handle_item_salvage)
    app.router.add_post("/api/game/craft/start", handle_craft_start)
    app.router.add_post("/api/game/craft/claim", handle_craft_claim)
    app.router.add_get("/api/game/forge/options", handle_forge_options)
    app.router.add_post("/api/game/forge/start", handle_forge_start)
    app.router.add_post("/api/game/forge/claim", handle_forge_claim)
    app.router.add_get("/api/game/battle-pass", handle_battle_pass_get)
    app.router.add_post("/api/game/battle-pass/claim", handle_battle_pass_claim)
    app.router.add_post("/api/game/battle-pass/playtime", handle_battle_pass_playtime)
    app.router.add_post("/api/game/battle-pass/unlock-premium", handle_battle_pass_unlock_premium)
    app.router.add_post("/api/game/daily-login/claim", handle_daily_login_claim)
    app.router.add_get("/api/game/talents", handle_talents_get)
    app.router.add_post("/api/game/talents/allocate", handle_talents_allocate)
    app.router.add_post("/api/game/talents/respec", handle_talents_respec)
    app.router.add_post("/api/game/item/use", handle_item_use)
    app.router.add_post("/api/game/item/enhance", handle_item_enhance)
    app.router.add_get("/api/game/item/enhance/info", handle_item_enhance_info)
    app.router.add_get("/api/game/shop/catalog", handle_shop_catalog)
    app.router.add_post("/api/game/shop/buy", handle_shop_buy)
    app.router.add_get("/api/game/market/listings", handle_market_listings)
    app.router.add_get("/api/game/market/history", handle_market_history)
    app.router.add_post("/api/game/market/list-item", handle_list_item_on_market)
    app.router.add_post("/api/game/market/buy", handle_market_buy)
    app.router.add_get("/api/game/milestones", handle_milestones)
    app.router.add_get("/api/game/reputation", handle_reputation)
    app.router.add_get("/api/game/auction/listings", handle_auction_listings)
    app.router.add_post("/api/game/auction/create", handle_auction_create)
    app.router.add_post("/api/game/auction/bid", handle_auction_bid)
    app.router.add_post("/api/game/auction/buyout", handle_auction_buyout)
    app.router.add_post("/api/game/auction/cancel", handle_auction_cancel)
    app.router.add_post("/api/game/blacksmith/buy-protection", handle_buy_protection)
    app.router.add_post("/api/game/guild/create", handle_guild_create)
    app.router.add_post("/api/game/guild/checkin", handle_guild_checkin_post)
    app.router.add_get("/api/game/guild/me", handle_guild_me)
    app.router.add_post("/api/game/guild/quests/claim", handle_guild_quest_claim)
    app.router.add_get("/api/game/guild/invite/candidates", handle_guild_invite_candidates)
    app.router.add_post("/api/game/guild/invite/send", handle_guild_invite_send)
    app.router.add_post("/api/game/guild/bank/deposit", handle_guild_bank_deposit)
    app.router.add_post("/api/game/guild/bank/withdraw", handle_guild_bank_withdraw)
    app.router.add_get("/api/game/guild/feed", handle_guild_feed_get)
    app.router.add_post("/api/game/guild/feed", handle_guild_feed_post)
    app.router.add_post("/api/game/guild/boss/start", handle_guild_boss_start)
    app.router.add_post("/api/game/guild/boss/hit", handle_guild_boss_hit)
    app.router.add_post("/api/game/guild/tech/unlock", handle_guild_tech_unlock)
    app.router.add_post("/api/game/guild/tech/contribute", handle_guild_tech_contribute)
    app.router.add_post("/api/game/guild/tech/finalize", handle_guild_tech_finalize)
    app.router.add_post("/api/game/guild/raid/create", handle_guild_raid_create)
    app.router.add_post("/api/game/guild/raid/signup", handle_guild_raid_signup)
    app.router.add_post("/api/game/guild/raid/start", handle_guild_raid_start)
    app.router.add_post("/api/game/guild/raid/strike", handle_guild_raid_strike)
    app.router.add_get("/api/game/guild/raid/state", handle_guild_raid_state)
    app.router.add_post("/api/game/guild/raid/bonus/start", handle_guild_raid_bonus_start)
    app.router.add_post("/api/game/guild/raid/cancel", handle_guild_raid_cancel)
    app.router.add_post("/api/game/guild/raid/complete", handle_guild_raid_complete)
    app.router.add_get("/api/game/combat/enemies", handle_combat_enemies)
    app.router.add_get("/api/game/dungeons", handle_game_dungeons)
    app.router.add_get("/api/game/dungeon/party/status", handle_dungeon_party_status)
    app.router.add_post("/api/game/dungeon/party/create", handle_dungeon_party_create)
    app.router.add_post("/api/game/dungeon/party/invite", handle_dungeon_party_invite)
    app.router.add_get("/api/game/dungeon/party/players", handle_dungeon_party_players)
    app.router.add_get("/api/game/dungeon/party/invites", handle_dungeon_party_invites_list)
    app.router.add_post("/api/game/dungeon/party/invite/accept", handle_dungeon_party_invite_accept)
    app.router.add_post("/api/game/dungeon/party/invite/decline", handle_dungeon_party_invite_decline)
    app.router.add_delete("/api/game/dungeon/party/invite", handle_dungeon_party_invite_cancel)
    app.router.add_post("/api/game/dungeon/party/enter", handle_dungeon_party_enter)
    app.router.add_post("/api/game/dungeon/party/join", handle_dungeon_party_join)
    app.router.add_post("/api/game/dungeon/party/leave", handle_dungeon_party_leave)
    app.router.add_get("/api/game/combat/state", handle_combat_state)
    app.router.add_post("/api/game/combat/state/ack", handle_combat_state_ack)
    app.router.add_post("/api/game/combat/start", handle_combat_start)
    app.router.add_post("/api/game/combat/action", handle_combat_action)
    app.router.add_post("/api/game/rest", handle_rest)
    app.router.add_get("/api/game/repair/quote", handle_repair_quote)
    app.router.add_post("/api/game/repair", handle_repair_post)
    app.router.add_get("/api/game/daily", handle_daily_quest_get)
    app.router.add_get("/api/game/prestige", handle_prestige_get)
    app.router.add_post("/api/game/prestige", handle_prestige_post)
    app.router.add_get("/api/game/trades", handle_trades_get)
    app.router.add_post("/api/game/trades/offer", handle_trade_offer_post)
    app.router.add_post("/api/game/trades/act", handle_trade_act_post)
    app.router.add_get("/api/game/idle/rewards", handle_idle_rewards_get)
    app.router.add_post("/api/game/idle/claim", handle_idle_claim_post)
    app.router.add_get("/api/game/pvp/status", handle_pvp_status)
    app.router.add_post("/api/game/pvp/queue", handle_pvp_queue_post)
    app.router.add_delete("/api/game/pvp/queue", handle_pvp_queue_delete)
    app.router.add_post("/api/game/pvp/challenge", handle_pvp_challenge)
    app.router.add_get("/api/game/pvp/players", handle_pvp_player_search)
    app.router.add_get("/api/game/social/roster", handle_social_roster)
    app.router.add_get("/api/game/social/settings", handle_social_settings_get)
    app.router.add_post("/api/game/social/settings", handle_social_settings_post)
    app.router.add_get("/api/game/social/suggestions", handle_social_suggestions)
    app.router.add_get("/api/game/social/whispers/inbox", handle_social_whispers_inbox)
    app.router.add_get("/api/game/social/requests", handle_social_requests)
    app.router.add_get("/api/game/social/players", handle_social_players_search)
    app.router.add_post("/api/game/social/friend/request", handle_social_friend_request)
    app.router.add_post("/api/game/social/friend/accept", handle_social_friend_accept)
    app.router.add_post("/api/game/social/friend/decline", handle_social_friend_decline)
    app.router.add_post("/api/game/social/friend/cancel", handle_social_friend_cancel)
    app.router.add_delete("/api/game/social/friend", handle_social_friend_delete)
    app.router.add_get("/api/game/social/ignore", handle_social_ignore_list)
    app.router.add_post("/api/game/social/ignore", handle_social_ignore_add)
    app.router.add_delete("/api/game/social/ignore", handle_social_ignore_delete)
    app.router.add_get("/api/game/social/whispers", handle_social_whispers_get)
    app.router.add_post("/api/game/social/whisper", handle_social_whisper_post)
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
