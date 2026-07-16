"""Identity → player resolution.

The one rule this module exists to enforce: **a player's id never changes.**

`players.id` is historically the Discord snowflake (database/db.py:1086) and 11
FK columns across 6 tables cascade off it, so re-keying a player is a migration,
not an update. Instead `auth_identities` maps (provider, provider_uid) → player_id,
and every login resolves through it:

    discord snowflake ─┐
                       ├─→ auth_identities ─→ players.id (immutable)
    game username ─────┘

Discord players keep their snowflake. Game-account players get a negative
synthetic id — Discord snowflakes are always positive (they are a millisecond
timestamp shifted left 22 bits), so the negative BIGINT space is permanently
free and the two can never collide. This scheme was chosen before this module
existed and pinned by tests/test_session_tokens.py:22.

Linking is an INSERT here. Resolving a link conflict re-points a row's player_id.
Neither touches players.id.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

log = logging.getLogger(__name__)

PROVIDER_DISCORD = "discord"
PROVIDER_NATIVE = "native"


async def allocate_native_id(db) -> int:
    """Reserve a fresh negative players.id for a game account.

    Uses a sequence rather than `MIN(id) - 1` so two concurrent signups cannot
    be handed the same id.
    """
    n = await db.fetchval("SELECT nextval('native_player_id_seq')")
    return -int(n)


async def resolve_identity(db, provider: str, provider_uid: str) -> Optional[int]:
    """player_id for a login, or None if this identity is unknown."""
    if not provider_uid:
        return None
    row = await db.fetchval(
        "SELECT player_id FROM auth_identities WHERE provider=$1 AND provider_uid=$2",
        provider,
        str(provider_uid),
    )
    return int(row) if row is not None else None


async def link_identity(db, provider: str, provider_uid: str, player_id: int) -> None:
    """Point an identity at a player. Idempotent for the same pair.

    Raises IdentityConflict if the identity already belongs to a *different*
    player — the caller must resolve that with the player, not silently steal it.
    """
    existing = await resolve_identity(db, provider, provider_uid)
    if existing is not None and existing != int(player_id):
        raise IdentityConflict(provider, str(provider_uid), existing, int(player_id))
    await db.execute(
        """
        INSERT INTO auth_identities (provider, provider_uid, player_id)
        VALUES ($1, $2, $3)
        ON CONFLICT (provider, provider_uid) DO NOTHING
        """,
        provider,
        str(provider_uid),
        int(player_id),
    )


async def repoint_identity(db, provider: str, provider_uid: str, player_id: int) -> None:
    """Move an identity to another player — the "which character do I keep?" answer.

    Nothing is deleted. The player row that loses the identity keeps its
    character, inventory and gold; it just becomes unreachable by that login.
    Re-pointing back restores it exactly, which is why this is safe to offer.
    """
    await db.execute(
        """
        INSERT INTO auth_identities (provider, provider_uid, player_id)
        VALUES ($1, $2, $3)
        ON CONFLICT (provider, provider_uid) DO UPDATE SET player_id = EXCLUDED.player_id
        """,
        provider,
        str(provider_uid),
        int(player_id),
    )


async def identities_for_player(db, player_id: int) -> list[dict[str, Any]]:
    rows = await db.fetch(
        "SELECT provider, provider_uid, created_at FROM auth_identities WHERE player_id=$1 ORDER BY created_at",
        int(player_id),
    )
    return [dict(r) for r in rows]


async def credentials_for_player(db, player_id: int) -> Optional[dict[str, Any]]:
    row = await db.fetchrow(
        """
        SELECT player_id, username, username_lc, email, email_lc, email_verified, created_at
        FROM player_credentials WHERE player_id=$1
        """,
        int(player_id),
    )
    return dict(row) if row else None


async def credentials_by_login(db, login: str) -> Optional[dict[str, Any]]:
    """Look up an account by username or email — players forget which they used."""
    key = (login or "").strip().lower()
    if not key:
        return None
    row = await db.fetchrow(
        """
        SELECT * FROM player_credentials
        WHERE username_lc = $1 OR email_lc = $1
        LIMIT 1
        """,
        key,
    )
    return dict(row) if row else None


class IdentityConflict(Exception):
    """An identity is already bound to a different player.

    Carries both player ids so the caller can show the player what they are
    choosing between rather than a dead end.
    """

    def __init__(self, provider: str, provider_uid: str, existing_player_id: int, requested_player_id: int):
        self.provider = provider
        self.provider_uid = provider_uid
        self.existing_player_id = existing_player_id
        self.requested_player_id = requested_player_id
        super().__init__(
            f"{provider} identity {provider_uid} is already linked to player {existing_player_id}"
        )
