from __future__ import annotations

import json
from typing import Any, Dict, List, Optional
from uuid import UUID

MAX_BODY_LEN = 400
FEED_PAGE = 40


async def post_chat(db, guild_id: UUID, author_character_id: UUID, body: str) -> tuple[bool, str]:
    text = (body or "").strip()
    if not text:
        return False, "Message is empty."
    if len(text) > MAX_BODY_LEN:
        return False, f"Message too long (max {MAX_BODY_LEN})."
    await db.execute(
        """
        INSERT INTO guild_feed_messages (guild_id, author_character_id, body, message_type)
        VALUES ($1, $2, $3, 'chat')
        """,
        guild_id,
        author_character_id,
        text,
    )
    return True, ""


async def post_system(
    db,
    guild_id: UUID,
    body: str,
    message_type: str = "system",
    meta: Optional[Dict[str, Any]] = None,
) -> None:
    await db.execute(
        """
        INSERT INTO guild_feed_messages (guild_id, author_character_id, body, message_type, meta)
        VALUES ($1, NULL, $2, $3, $4::jsonb)
        """,
        guild_id,
        body[:MAX_BODY_LEN],
        message_type,
        json.dumps(meta or {}),
    )


async def fetch_feed(
    db,
    guild_id: UUID,
    before_id: Optional[UUID] = None,
) -> List[Dict[str, Any]]:
    if before_id:
        rows = await db.fetch(
            """
            SELECT m.id, m.guild_id, m.author_character_id, m.body, m.message_type, m.meta, m.created_at,
                   c.name AS author_name
            FROM guild_feed_messages m
            LEFT JOIN characters c ON c.id = m.author_character_id
            WHERE m.guild_id = $1 AND m.id < $2
            ORDER BY m.created_at DESC, m.id DESC
            LIMIT $3
            """,
            guild_id,
            before_id,
            FEED_PAGE,
        )
    else:
        rows = await db.fetch(
            """
            SELECT m.id, m.guild_id, m.author_character_id, m.body, m.message_type, m.meta, m.created_at,
                   c.name AS author_name
            FROM guild_feed_messages m
            LEFT JOIN characters c ON c.id = m.author_character_id
            WHERE m.guild_id = $1
            ORDER BY m.created_at DESC, m.id DESC
            LIMIT $2
            """,
            guild_id,
            FEED_PAGE,
        )
    return [dict(r) for r in rows]
