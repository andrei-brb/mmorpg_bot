"""
╔══════════════════════════════════════════════════════════════════════════════╗
║   cogs/activity/activity_cog.py — /activity (how to open the game client)    ║
║   /open_game — LAUNCH_ACTIVITY (opens Embedded App in the Discord client)   ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import logging
import os

import discord
from discord import app_commands
from discord.ext import commands
from discord.webhook.async_ import async_context, interaction_response_params

log = logging.getLogger("cog.activity")


async def respond_launch_activity(interaction: discord.Interaction) -> None:
    """
    Tell Discord to open this application's Embedded Activity (iframe).
    API: interaction response type 12 — LAUNCH_ACTIVITY.
    See https://docs.discord.com/developers/activities/how-activities-work
    """
    if interaction.response.is_done():
        raise discord.InteractionResponded(interaction)

    adapter = async_context.get()
    params = interaction_response_params(12)  # LAUNCH_ACTIVITY (no data payload)
    http = interaction._state.http

    await adapter.create_interaction_response(
        interaction.id,
        interaction.token,
        session=interaction._session,
        proxy=http.proxy,
        proxy_auth=http.proxy_auth,
        params=params,
    )
    # discord.py 2.3 has no enum member for type 12 — mark as responded.
    interaction.response._response_type = discord.InteractionResponseType.channel_message


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
            name="1 · Bot env (OAuth + API)",
            value=(
                "Set **`DISCORD_CLIENT_SECRET`** (OAuth2 page) and **`DISCORD_APPLICATION_ID`** (same as Application ID).\n"
                "The bot exposes **`POST /api/token`** and **`GET /api/game/inventory`** on **`PORT`** (e.g. Railway).\n"
                "See **`ACTIVITY_SETUP.md`** for full list."
            ),
            inline=False,
        )
        embed.add_field(
            name="2 · Build & URL mapping",
            value=(
                "Build: `cd activity && npm ci && npm run build` (or Docker build-arg `VITE_DISCORD_CLIENT_ID`).\n"
                "**Activities** → **URL Mappings**: prefix `/` → your **HTTPS** public URL (same host as API if possible)."
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
        embed.add_field(
            name="Fastest: slash command",
            value="Use **`/open_game`** in this server — Discord should open the Activity iframe (no voice search needed).",
            inline=False,
        )
        embed.set_footer(text="See ACTIVITY_SETUP.md in the repo for full steps.")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(
        name="open_game",
        description="Open the World of Discord embedded app (Activity) in Discord",
    )
    async def open_game(self, interaction: discord.Interaction):
        from services.channel_manager import check_channel

        if not await check_channel(interaction, "activity"):
            return

        try:
            await respond_launch_activity(interaction)
        except discord.HTTPException as e:
            log.warning("open_game LAUNCH_ACTIVITY failed: %s", e)
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "Could not open the Activity. Check the Developer Portal → **Activities** are enabled "
                    f"for this app, URL mapping is set, and the client is up to date.\n\n"
                    f"Discord said: `{e}`",
                    ephemeral=True,
                )
        except Exception as e:
            log.exception("open_game failed")
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    f"Something went wrong opening the Activity: `{e}`",
                    ephemeral=True,
                )


async def setup(bot: commands.Bot):
    await bot.add_cog(ActivityCog(bot))
