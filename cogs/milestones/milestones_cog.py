"""
Server milestones commands.
"""

import logging

import discord
from discord import app_commands
from discord.ext import commands

from services.milestones.milestone_service import MilestoneService

log = logging.getLogger("cog.milestones")


def _bar(current: int, target: int, length: int = 16) -> str:
    if target <= 0:
        return "█" * length
    pct = max(0.0, min(1.0, current / target))
    filled = int(round(length * pct))
    return "█" * filled + "░" * (length - filled)


class MilestonesCog(commands.Cog, name="Milestones"):
    def __init__(self, bot):
        self.bot = bot
        self.svc: MilestoneService | None = None

    async def cog_load(self):
        self.svc = MilestoneService(self.bot.db)

    @app_commands.command(name="milestones", description="View server milestone progress and active buffs")
    async def milestones(self, interaction: discord.Interaction):
        if not interaction.guild_id:
            return await interaction.response.send_message(
                "❌ Milestones are only available in servers.", ephemeral=True
            )
        await interaction.response.defer(ephemeral=True)

        progress = await self.svc.get_progress(interaction.guild_id)
        buffs = await self.svc.get_active_buffs(interaction.guild_id)

        embed = discord.Embed(
            title="🏁 Server Milestones",
            description="Shared progression for this server.",
            color=0xF1C40F,
        )

        for row in progress:
            cur = int(row["value"])
            nxt = row["next_target"]
            if nxt:
                pct = int((cur / nxt) * 100) if nxt > 0 else 100
                value = f"`{_bar(cur, nxt)}` **{cur:,}/{nxt:,} {row['unit']}** ({pct}%)"
            else:
                value = f"`{'█'*16}` **{cur:,} {row['unit']}** (MAX)"
            embed.add_field(
                name=f"{row['title']} — Tier {row['tier']}/{row['max_tier']}",
                value=value,
                inline=False,
            )

        if buffs:
            buff_lines = []
            for b in buffs[:8]:
                label = "XP" if b["buff_type"] == "xp_multiplier" else "Gold"
                pct = int(float(b["buff_value"]) * 100)
                ts = int(b["expires_at"].timestamp())
                buff_lines.append(f"• **{label} +{pct}%** until <t:{ts}:R>")
            embed.add_field(name="✨ Active Server Buffs", value="\n".join(buff_lines), inline=False)
        else:
            embed.add_field(name="✨ Active Server Buffs", value="None active.", inline=False)

        embed.set_footer(text="Milestones update automatically from gameplay.")
        await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(MilestonesCog(bot))
