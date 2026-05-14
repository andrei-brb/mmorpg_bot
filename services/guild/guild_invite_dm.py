"""Discord DM for guild invites — shared by `/guild invite` and Activity HTTP."""

from __future__ import annotations

import logging
from typing import Any, Mapping

import discord

log = logging.getLogger(__name__)


def build_guild_invite_embed(guild: Mapping[str, Any], inviter_name: str) -> discord.Embed:
    embed = discord.Embed(
        title="🏰 Guild Invitation",
        description=f"**{inviter_name}** has invited you to join **[{guild['tag']}] {guild['name']}**!",
        color=0xFFD700,
    )
    embed.add_field(name="Guildmaster", value=guild.get("guildmaster_name", "Unknown"), inline=True)
    embed.add_field(
        name="Members",
        value=f"{guild['member_count']}/{guild['max_members']}",
        inline=True,
    )
    return embed


class GuildInviteView(discord.ui.View):
    """Accept / decline in DMs; mutates `characters` + `guilds.member_count` like the legacy cog."""

    def __init__(self, guild_id: Any, bot: discord.Client, char_svc: Any) -> None:
        super().__init__(timeout=300)
        self.guild_id = guild_id
        self.bot = bot
        self.char_svc = char_svc

    @discord.ui.button(label="✅ Accept", style=discord.ButtonStyle.green)
    async def accept(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        target = await self.char_svc.get_character(interaction.user.id)
        if not target:
            return await interaction.followup.send("❌ No character found.")
        if target["guild_id"]:
            return await interaction.followup.send("❌ You're already in a guild.")

        guild = await self.bot.db.fetchrow("SELECT * FROM guilds WHERE id=$1", self.guild_id)
        if not guild:
            return await interaction.followup.send("❌ Guild no longer exists.")
        if guild["member_count"] >= guild["max_members"]:
            return await interaction.followup.send("❌ Guild is now full.")

        await self.bot.db.execute(
            "UPDATE characters SET guild_id=$1, guild_rank='member' WHERE id=$2",
            self.guild_id,
            target["id"],
        )
        await self.bot.db.execute(
            """
            UPDATE guilds SET member_count=(
                SELECT COUNT(*)::int FROM characters WHERE guild_id=$1
            ) WHERE id=$1
            """,
            self.guild_id,
        )
        await interaction.followup.send(f"✅ You joined **[{guild['tag']}] {guild['name']}**!")
        self.stop()

    @discord.ui.button(label="❌ Decline", style=discord.ButtonStyle.red)
    async def decline(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        await interaction.followup.send("❌ Invitation declined.")
        self.stop()
