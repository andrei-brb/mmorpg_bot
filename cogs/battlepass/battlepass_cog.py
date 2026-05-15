"""Discord slash commands for battle pass (view + admin reset)."""

from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.ext import commands

from services.battle_pass.battle_pass_service import BattlePassService
from services.character.character_service import CharacterService

log = logging.getLogger("cog.battlepass")


class BattlePassCog(commands.Cog, name="BattlePass"):
    def __init__(self, bot):
        self.bot = bot
        self.svc = CharacterService(bot.db)

    battlepass = app_commands.Group(name="battlepass", description="Seasonal battle pass")

    @battlepass.command(name="status", description="View your battle pass progress")
    async def battlepass_status(self, interaction: discord.Interaction):
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        char = await self.svc.get_character(interaction.user.id)
        if not char:
            return await interaction.followup.send("❌ No character — use `/character create`.", ephemeral=True)

        bp = BattlePassService(self.bot.db)
        state = await bp.get_state(char["id"])
        season = state.get("season")
        prog = state.get("progress") or {}
        daily = state.get("daily_login") or {}

        if not season:
            return await interaction.followup.send("No battle pass season is active.", ephemeral=True)

        embed = discord.Embed(
            title=f"🎫 {season.get('name', 'Battle Pass')}",
            color=0xC9A227,
        )
        embed.add_field(
            name="Progress",
            value=(
                f"Tier **{prog.get('tier', 0)}** / {season.get('max_tier', 30)}\n"
                f"Pass XP: **{prog.get('xp', 0):,}**"
            ),
            inline=True,
        )
        embed.add_field(
            name="Login streak",
            value=f"🔥 **{daily.get('current_streak', 0)}** days",
            inline=True,
        )
        if daily.get("weekend_double"):
            embed.set_footer(text="Weekend: double pass XP active (UTC)")
        await interaction.followup.send(embed=embed, ephemeral=True)

    @battlepass.command(name="admin", description="Admin: reset battle pass season (pre-launch testing)")
    @app_commands.describe(restart_now="Start a fresh 28-day season immediately")
    async def battlepass_admin_reset(
        self, interaction: discord.Interaction, restart_now: bool = True
    ):
        if not BattlePassService.is_admin_discord_id(interaction.user.id):
            return await interaction.response.send_message(
                "❌ Not authorized. Set `BATTLE_PASS_ADMIN_DISCORD_IDS` with your Discord user id.",
                ephemeral=True,
            )
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        bp = BattlePassService(self.bot.db)
        ok, msg = await bp.admin_reset_season(restart_now=restart_now)
        prefix = "✅" if ok else "❌"
        await interaction.followup.send(f"{prefix} {msg}", ephemeral=True)


async def setup(bot):
    await bot.add_cog(BattlePassCog(bot))
