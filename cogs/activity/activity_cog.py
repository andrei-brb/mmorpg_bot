"""
╔══════════════════════════════════════════════════════════════════════════════╗
║   cogs/activity/activity_cog.py — /activity (how to open the game client)    ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import os

import discord
from discord import app_commands
from discord.ext import commands


class ActivityCog(commands.Cog, name="Activity"):
    """Instructions for launching the Discord Embedded App (Activity)."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="activity",
        description="How to open the visual game client (Discord Activity)",
    )
    async def activity(self, interaction: discord.Interaction):
        from services.channel_manager import check_channel

        if not await check_channel(interaction, "activity"):
            return

        app_id = interaction.client.application_id
        if app_id is None:
            app_id = os.getenv("DISCORD_APPLICATION_ID", "").strip()
        app_part = f"\n**Application ID:** `{app_id}`\n" if app_id else ""

        embed = discord.Embed(
            title="🖥️ Open the Activity (visual client)",
            description=(
                "The **bot** handles saves, economy, and slash commands. The **Activity** is the "
                "mini web UI inside Discord (inventory grid, equipment — we’re building it out).\n"
                f"{app_part}"
            ),
            color=0x7C5CFF,
        )
        embed.add_field(
            name="1 · Deploy or tunnel your Activity URL",
            value=(
                "Build the web app: `cd activity && npm ci && npm run build`\n"
                "Host the `activity/dist` folder on **HTTPS** (e.g. Vercel, Cloudflare Pages, Netlify), "
                "or use **ngrok** for local testing."
            ),
            inline=False,
        )
        embed.add_field(
            name="2 · Developer Portal → URL Mapping",
            value=(
                "**Discord Developer Portal** → your app → **Activities** → **URL Mappings**\n"
                "• Prefix: `/` → Target URL: `https://your-site.example` (no trailing slash)\n"
                "Use the same **Application ID** as `VITE_DISCORD_CLIENT_ID` in `activity/.env`."
            ),
            inline=False,
        )
        embed.add_field(
            name="3 · Launch inside Discord",
            value=(
                "• **Join a voice channel** in a server where the bot is installed.\n"
                "• Click the **rocket** (Activities) or **Open Activity** near the voice controls.\n"
                "• Pick **this application** — the iframe loads your hosted URL.\n\n"
                "**Desktop:** Left sidebar → voice channel → rocket icon.\n"
                "**Mobile:** Voice channel → look for Activities / launcher.\n\n"
                "If you don’t see it: confirm **Activities** is enabled for the app in the portal "
                "and that URL mapping is saved."
            ),
            inline=False,
        )
        embed.set_footer(text="See ACTIVITY_SETUP.md in the repo for full steps.")
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(ActivityCog(bot))
