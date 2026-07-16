"""Server-issued session tokens (HS256 JWT) for standalone (non-Discord-host) clients.

The Discord Activity sends a raw Discord bearer that the backend validates
against Discord's `/users/@me`. Standalone clients (the mobile app, or a
standalone web Discord login) can't rely on the Discord host, so after a
one-time login we issue our OWN signed session token. Requests carrying it are
authenticated locally — no per-request Discord round-trip.

Hand-rolled HS256 (stdlib only) to avoid a new dependency; symmetric signing is
all we need for tokens we both issue and verify. (Provider tokens from
Apple/Google are RS256/JWKS — verified separately in Phase 2.)
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
import time
from typing import Any, Dict, Optional

log = logging.getLogger("auth.session")

DEFAULT_TTL_SECONDS = 30 * 24 * 3600  # 30 days
_ALG = "HS256"


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64url_decode(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)


def _secret() -> bytes:
    """Signing key. Prefer a dedicated SESSION_JWT_SECRET; otherwise derive a
    domain-separated key from the Discord client secret (stable across restarts,
    not literally the same key). Dev-only constant as a last resort, loudly."""
    explicit = (os.getenv("SESSION_JWT_SECRET") or "").strip()
    if explicit:
        return explicit.encode("utf-8")
    discord_secret = (os.getenv("DISCORD_CLIENT_SECRET") or "").strip()
    if discord_secret:
        return hashlib.sha256(b"session-token:" + discord_secret.encode("utf-8")).digest()
    log.warning(
        "SESSION_JWT_SECRET and DISCORD_CLIENT_SECRET are unset — using an INSECURE "
        "dev signing key. Set SESSION_JWT_SECRET in production."
    )
    return b"insecure-dev-session-secret-do-not-use-in-prod"


def issue_session(
    player_id: int,
    provider: str,
    *,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
    identity: Optional[Dict[str, Any]] = None,
    now: Optional[int] = None,
) -> str:
    """Sign a session token for `player_id`. `identity` (optional) carries display
    fields (username/global_name/avatar) so authed handlers can render a name
    without a DB or Discord lookup."""
    issued = int(now if now is not None else time.time())
    claims: Dict[str, Any] = {
        "sub": int(player_id),
        "prov": provider,
        "iat": issued,
        "exp": issued + int(ttl_seconds),
    }
    if identity:
        # Compact keys mirror the Discord user shape consumers already read.
        if identity.get("username") is not None:
            claims["un"] = identity["username"]
        if identity.get("global_name") is not None:
            claims["gn"] = identity["global_name"]
        if identity.get("avatar") is not None:
            claims["av"] = identity["avatar"]

    header = {"alg": _ALG, "typ": "JWT"}
    signing_input = (
        _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
        + "."
        + _b64url_encode(json.dumps(claims, separators=(",", ":")).encode("utf-8"))
    )
    sig = hmac.new(_secret(), signing_input.encode("ascii"), hashlib.sha256).digest()
    return signing_input + "." + _b64url_encode(sig)


def verify_session(token: str, *, now: Optional[int] = None) -> Optional[Dict[str, Any]]:
    """Return the claims dict if `token` is one of our valid, unexpired session
    tokens; otherwise None (so callers can fall back to the Discord bearer path).
    Never raises."""
    if not token or token.count(".") != 2:
        return None
    try:
        header_b64, payload_b64, sig_b64 = token.split(".")
        header = json.loads(_b64url_decode(header_b64))
        if header.get("alg") != _ALG:
            return None
        signing_input = f"{header_b64}.{payload_b64}"
        expected = hmac.new(_secret(), signing_input.encode("ascii"), hashlib.sha256).digest()
        if not hmac.compare_digest(expected, _b64url_decode(sig_b64)):
            return None
        claims = json.loads(_b64url_decode(payload_b64))
        if not isinstance(claims, dict) or "sub" not in claims:
            return None
        exp = int(claims.get("exp") or 0)
        current = int(now if now is not None else time.time())
        if exp and current >= exp:
            return None
        return claims
    except Exception:
        return None


_LINK_TTL_SECONDS = 10 * 60


def issue_link_intent(
    player_id: int,
    provider: str,
    provider_uid: str,
    *,
    ttl_seconds: int = _LINK_TTL_SECONDS,
    now: Optional[int] = None,
) -> str:
    """Short-lived proof of "this player proved they own this identity".

    Linking can hit a conflict — the Discord account already has its own
    character — and the player then has to choose which one to keep. This token
    carries that pending decision across the round-trip so they don't have to
    re-do the whole OAuth dance to answer.

    SECURITY: it deliberately carries NO `sub` claim, so verify_session rejects
    it (see the "sub" check above). A token that could both describe a pending
    link AND authenticate as its subject would let anyone who obtained one act
    as that player. Same key, different shape, non-interchangeable.
    """
    issued = int(now if now is not None else time.time())
    claims: Dict[str, Any] = {
        "typ": "link",
        "pid": int(player_id),          # who is asking to link
        "prov": str(provider),
        "uid": str(provider_uid),       # the identity they proved they own
        "iat": issued,
        "exp": issued + int(ttl_seconds),
    }
    header = {"alg": _ALG, "typ": "JWT"}
    h = _b64url_encode(json.dumps(header, separators=(",", ":")).encode())
    p = _b64url_encode(json.dumps(claims, separators=(",", ":")).encode())
    sig = hmac.new(_secret(), f"{h}.{p}".encode("ascii"), hashlib.sha256).digest()
    return f"{h}.{p}.{_b64url_encode(sig)}"


def verify_link_intent(token: str, *, now: Optional[int] = None) -> Optional[Dict[str, Any]]:
    """Claims for a valid link-intent token, else None. Never raises.

    Requires typ == "link", so a real session token cannot be replayed here
    either — the rejection runs in both directions.
    """
    if not token or token.count(".") != 2:
        return None
    try:
        h, p, s = token.split(".")
        if json.loads(_b64url_decode(h)).get("alg") != _ALG:
            return None
        expected = hmac.new(_secret(), f"{h}.{p}".encode("ascii"), hashlib.sha256).digest()
        if not hmac.compare_digest(expected, _b64url_decode(s)):
            return None
        claims = json.loads(_b64url_decode(p))
        if not isinstance(claims, dict) or claims.get("typ") != "link":
            return None
        if "pid" not in claims or "uid" not in claims:
            return None
        exp = int(claims.get("exp") or 0)
        if exp and int(now if now is not None else time.time()) >= exp:
            return None
        return claims
    except Exception:
        return None


def identity_from_claims(claims: Dict[str, Any]) -> Dict[str, Any]:
    """Reconstruct a Discord-user-shaped dict from session claims so existing
    handlers (which read id/username/global_name/avatar) work unchanged."""
    return {
        "id": str(claims.get("sub")),
        "username": claims.get("un"),
        "global_name": claims.get("gn"),
        "avatar": claims.get("av"),
    }
