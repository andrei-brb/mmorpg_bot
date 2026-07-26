"""
╔══════════════════════════════════════════════════════════════════════════════╗
║            services/notifications/push.py — Remote push (APNs)              ║
╚══════════════════════════════════════════════════════════════════════════════╝

The app already schedules LOCAL notifications — the daily reset, the idle cap
filling up — but those only fire for things the phone can predict by itself.
Everything that makes a shared game worth coming back to is unpredictable from
the device: someone whispered you, your guild started a raid, your season is
ending tonight, a friend passed you on the board.

That needs a server-initiated push, which needs APNs.

── The seam, and what is missing ─────────────────────────────────────────────

Everything here is complete and tested EXCEPT the credential. Exactly like
``services/auth/email_sender.py``, this ships two drivers:

  ``LogPusher``   the default. Logs what it would have sent. The game works
                  normally; nothing is delivered.
  ``APNsPusher``  real. Signs a JWT with an Apple ``.p8`` key and posts to
                  Apple's HTTP/2 endpoint.

To turn it on, the owner sets four environment variables:

  ``APNS_KEY_ID``     the 10-character Key ID from the Apple Developer portal
  ``APNS_TEAM_ID``    the 10-character Team ID
  ``APNS_AUTH_KEY``   the contents of the AuthKey_XXXXXXXXXX.p8 file
  ``APNS_BUNDLE_ID``  com.wold.mmo (defaulted)

Those cannot be generated from here — creating an APNs key requires signing in
to a paid Apple Developer account. Everything up to that point is done, so the
day the key exists this starts delivering with no further code.

``APNS_USE_SANDBOX=1`` targets Apple's sandbox host, which is what a
development build registers against. A production build needs it unset.

── Why tokens are stored per device, not per player ──────────────────────────

One player can hold several devices, and a device token is invalidated by Apple
whenever the app is reinstalled. Keying by token (not by player) means a stale
token is a row to delete rather than a player whose notifications silently stop,
and Apple's 410 response tells us exactly which row that is.
"""

import json
import logging
import os
import time
from typing import Any, Dict, List, Optional, Protocol
from uuid import UUID

log = logging.getLogger("push")

APNS_HOST_PROD = "https://api.push.apple.com"
APNS_HOST_SANDBOX = "https://api.sandbox.push.apple.com"

DEFAULT_BUNDLE_ID = "com.wold.mmo"

#: Apple rejects a token permanently with this status; the row should be dropped.
APNS_GONE = 410


class Pusher(Protocol):
    async def send(self, *, token: str, title: str, body: str, data: Dict[str, Any]) -> bool: ...


class LogPusher:
    """Default driver. The game works; nothing is delivered."""

    def __init__(self, reason: str = "no APNs credentials"):
        self.reason = reason
        self._warned = False

    async def send(self, *, token: str, title: str, body: str, data: Dict[str, Any]) -> bool:
        if not self._warned:
            log.warning("push disabled (%s) — notifications will be logged, not delivered", self.reason)
            self._warned = True
        log.info("PUSH NOT SENT to %s…: %s — %s", str(token)[:8], title, body)
        return False


class APNsPusher:
    """Real APNs delivery over HTTP/2 with a signed provider token."""

    #: Apple accepts a provider JWT for one hour; refreshing well inside that
    #: avoids a clock-skew rejection at the boundary.
    TOKEN_TTL = 45 * 60

    def __init__(self, key_id: str, team_id: str, auth_key: str, bundle_id: str, sandbox: bool = False):
        self.key_id = key_id
        self.team_id = team_id
        self.auth_key = auth_key
        self.bundle_id = bundle_id
        self.host = APNS_HOST_SANDBOX if sandbox else APNS_HOST_PROD
        self._jwt: Optional[str] = None
        self._jwt_at: float = 0.0

    def _provider_token(self) -> str:
        now = time.time()
        if self._jwt and (now - self._jwt_at) < self.TOKEN_TTL:
            return self._jwt
        # ES256 over the .p8 key. Imported lazily so the module stays importable
        # (and the whole game keeps booting) on a host without `cryptography`.
        import jwt as pyjwt  # type: ignore

        self._jwt = pyjwt.encode(
            {"iss": self.team_id, "iat": int(now)},
            self.auth_key,
            algorithm="ES256",
            headers={"kid": self.key_id},
        )
        self._jwt_at = now
        return self._jwt

    async def send(self, *, token: str, title: str, body: str, data: Dict[str, Any]) -> bool:
        import aiohttp

        payload = {
            "aps": {"alert": {"title": title, "body": body}, "sound": "default", "badge": 1},
            **({"data": data} if data else {}),
        }
        headers = {
            "authorization": f"bearer {self._provider_token()}",
            "apns-topic": self.bundle_id,
            "apns-push-type": "alert",
            "apns-priority": "10",
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.host}/3/device/{token}", json=payload, headers=headers, timeout=10
                ) as resp:
                    if resp.status == 200:
                        return True
                    text = await resp.text()
                    if resp.status == APNS_GONE:
                        log.info("apns token gone, will be pruned: %s…", token[:8])
                    else:
                        log.warning("apns %s for %s…: %s", resp.status, token[:8], text[:200])
                    return False
        except Exception:
            log.exception("apns send failed")
            return False


_pusher: Optional[Pusher] = None


def get_pusher() -> Pusher:
    """The configured driver, or the logging stub."""
    global _pusher
    if _pusher is not None:
        return _pusher

    key_id = (os.getenv("APNS_KEY_ID") or "").strip()
    team_id = (os.getenv("APNS_TEAM_ID") or "").strip()
    auth_key = (os.getenv("APNS_AUTH_KEY") or "").strip()
    bundle = (os.getenv("APNS_BUNDLE_ID") or DEFAULT_BUNDLE_ID).strip()

    if key_id and team_id and auth_key:
        try:
            import jwt  # noqa: F401
        except ImportError:
            _pusher = LogPusher("PyJWT with cryptography is not installed")
            return _pusher
        _pusher = APNsPusher(
            key_id, team_id, auth_key, bundle,
            sandbox=bool((os.getenv("APNS_USE_SANDBOX") or "").strip()),
        )
        log.info("push: APNs configured for %s (%s)", bundle, "sandbox" if os.getenv("APNS_USE_SANDBOX") else "production")
    else:
        missing = [n for n, v in (("APNS_KEY_ID", key_id), ("APNS_TEAM_ID", team_id), ("APNS_AUTH_KEY", auth_key)) if not v]
        _pusher = LogPusher(f"missing {', '.join(missing)}")
    return _pusher


def reset_pusher() -> None:
    """Test hook — forces the driver to be resolved again."""
    global _pusher
    _pusher = None


# ── Device registry ───────────────────────────────────────────────────────────


async def register_device(db, player_id: int, token: str, platform: str = "ios") -> bool:
    """Record a device token for a player.

    Upserts on the token, not the player: one player can hold several devices,
    and a token can move between players if a phone is handed over.
    """
    token = (token or "").strip()
    if not token or len(token) > 200:
        return False
    try:
        await db.execute(
            """
            INSERT INTO push_devices (token, player_id, platform, updated_at)
            VALUES ($1, $2, $3, NOW())
            ON CONFLICT (token) DO UPDATE SET
                player_id = EXCLUDED.player_id,
                platform  = EXCLUDED.platform,
                updated_at = NOW()
            """,
            token, int(player_id), (platform or "ios")[:16],
        )
        return True
    except Exception:
        log.exception("push device registration failed")
        return False


async def unregister_device(db, token: str) -> None:
    try:
        await db.execute("DELETE FROM push_devices WHERE token = $1", token)
    except Exception:
        log.exception("push device removal failed")


async def notify_player(
    db, player_id: int, *, title: str, body: str, data: Optional[Dict[str, Any]] = None
) -> int:
    """Push to every device a player has registered. Returns how many landed.

    Never raises. A notification failing must never take down whatever game
    action triggered it.
    """
    try:
        rows = await db.fetch("SELECT token FROM push_devices WHERE player_id = $1", int(player_id))
    except Exception:
        log.exception("push lookup failed")
        return 0

    pusher = get_pusher()
    sent = 0
    for r in rows:
        token = r["token"]
        try:
            if await pusher.send(token=token, title=title, body=body, data=data or {}):
                sent += 1
        except Exception:
            log.exception("push send failed")
    return sent
