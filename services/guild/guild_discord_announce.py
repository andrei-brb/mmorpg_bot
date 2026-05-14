"""Post updates to the guild's configured Discord text channel (`guilds.announce_channel_id`)."""

from __future__ import annotations

import logging
from typing import Any, Optional
from uuid import UUID

log = logging.getLogger("guild.discord_announce")


async def post_to_guild_announce_channel(
    bot: Any,
    db: Any,
    ingame_guild_id: UUID,
    *,
    text: Optional[str] = None,
    embed: Any = None,
) -> bool:
    """
    Send a message to `guilds.announce_channel_id` if set and the bot can access the channel.
    """
    if bot is None:
        return False
    if not text and embed is None:
        return False

    row = await db.fetchrow(
        "SELECT name, tag, announce_channel_id FROM guilds WHERE id = $1",
        ingame_guild_id,
    )
    if not row or row.get("announce_channel_id") is None:
        return False

    try:
        ch_id = int(row["announce_channel_id"])
    except (TypeError, ValueError):
        return False

    tag = (row.get("tag") or "?").strip()
    gname = (row.get("name") or "Guild").strip()

    try:
        import discord

        ch = bot.get_channel(ch_id)
        if ch is None:
            ch = await bot.fetch_channel(ch_id)
        if ch is None:
            log.debug("Announce channel %s not found for guild %s", ch_id, ingame_guild_id)
            return False

        if embed is not None and isinstance(embed, discord.Embed):
            embed.set_author(name=f"{gname} [{tag}]")
            await ch.send(content=text[:2000] if text else None, embed=embed)
        elif text:
            await ch.send(text[:2000])
        else:
            return False
        return True
    except Exception as e:
        log.warning("Guild Discord announce failed (guild=%s channel=%s): %s", ingame_guild_id, ch_id, e)
        return False
