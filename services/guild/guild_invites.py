"""Persistent guild invites — required for /guild join and DM accept flows."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from uuid import UUID


async def upsert_pending_invite(
    db,
    guild_id: UUID,
    invitee_player_id: int,
    *,
    inviter_character_id: Optional[UUID] = None,
    days: int = 7,
) -> None:
    """Create or refresh a pending invite (expires prior pending rows for same pair)."""
    expires_at = datetime.now(timezone.utc) + timedelta(days=days)
    # Expire-then-insert atomically so a concurrent call can't leave two pending rows.
    async with db.transaction() as tx:
        await tx.execute(
            """
            UPDATE guild_invites SET status='expired'
            WHERE guild_id=$1 AND invitee_player_id=$2 AND status='pending'
            """,
            guild_id,
            invitee_player_id,
        )
        await tx.execute(
            """
            INSERT INTO guild_invites (guild_id, invitee_player_id, inviter_character_id, expires_at)
            VALUES ($1, $2, $3, $4)
            """,
            guild_id,
            invitee_player_id,
            inviter_character_id,
            expires_at,
        )


async def get_valid_pending_invite(
    db, guild_id: UUID, invitee_player_id: int
) -> Optional[Any]:
    return await db.fetchrow(
        """
        SELECT id FROM guild_invites
        WHERE guild_id=$1 AND invitee_player_id=$2
          AND status='pending' AND expires_at > NOW()
        ORDER BY created_at DESC
        LIMIT 1
        """,
        guild_id,
        invitee_player_id,
    )


async def mark_invite_accepted(
    db, guild_id: UUID, invitee_player_id: int
) -> None:
    await db.execute(
        """
        UPDATE guild_invites SET status='accepted'
        WHERE guild_id=$1 AND invitee_player_id=$2 AND status='pending'
        """,
        guild_id,
        invitee_player_id,
    )


async def expire_stale_invites(db) -> None:
    await db.execute(
        """
        UPDATE guild_invites SET status='expired'
        WHERE status='pending' AND expires_at <= NOW()
        """
    )
