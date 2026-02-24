"""
╔══════════════════════════════════════════════════════════════════════════════╗
║           WORLD OF DISCORD — WoW-inspired Discord MMORPG Bot               ║
║                          main.py — Entry Point                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import asyncio
import logging
import os
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

# ── Logger setup ──────────────────────────────────────────────────────────────
log_level = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("bot")


# ── Custom CommandTree with channel routing ──────────────────────────────────

class GameCommandTree(app_commands.CommandTree):
    """Custom command tree that enforces channel routing and cooldowns."""

    async def interaction_check(self, interaction: discord.Interaction, /) -> bool:
        """Global pre-command check: cooldowns + channel routing."""
        bot = interaction.client

        # --- Cooldown ---
        if hasattr(bot, "cooldowns"):
            remaining = bot.cooldowns.check(interaction.user.id)
            if remaining:
                try:
                    await interaction.response.send_message(
                        f"⏳ Please wait **{remaining}s** before using another command.",
                        ephemeral=True,
                    )
                except Exception:
                    pass
                return False

        # --- Channel routing (only in guilds) ---
        if interaction.guild_id and hasattr(bot, "channels"):
            from services.channel_manager import check_channel
            allowed = await check_channel(interaction)
            if not allowed:
                return False  # Blocked — error message already sent

        return True


class MMORPGBot(commands.Bot):
    """
    Core bot class. Manages DB pool, cog loading, and lifecycle.
    All game logic lives in cogs and services — never here.
    """

    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True

        super().__init__(
            command_prefix="!",          # Legacy prefix (slash commands are primary)
            intents=intents,
            help_command=None,
            description="World of Discord",
            tree_cls=GameCommandTree,    # Use our custom tree with channel checks
        )

        # Injected in setup_hook so cogs can access via self.bot.db
        self.db = None

        # Anti-spam cooldown manager (per-user, 2s default)
        from services.channel_manager import CooldownManager, ChannelManager
        self.cooldowns = CooldownManager(default_cooldown=2.0)
        self.channels  = ChannelManager(self)

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def setup_hook(self):
        """Called once before bot connects. Set up DB and load all cogs."""
        from database.db import Database
        from config.settings import Settings

        log.info("Connecting to database...")
        self.db = Database(Settings.DATABASE_URL)
        await self.db.connect()
        await self.db.initialize_schema()
        log.info("✓ Database ready")

        # Hook tree error handler
        self.tree.on_error = self._handle_error

        log.info("Loading cogs...")

        cogs = [
            "cogs.character.character_cog",
            "cogs.combat.combat_cog",
            "cogs.exploration.exploration_cog",
            "cogs.inventory.inventory_cog",
            "cogs.guild.guild_cog",
            "cogs.economy.economy_cog",
            "cogs.events.events_cog",
            "cogs.dungeon.dungeon_cog",
            "cogs.achievements.achievements_cog",
            "cogs.admin.admin_cog",
            "cogs.blacksmith.blacksmith_cog",
            "cogs.help_cog",
        ]
        for cog in cogs:
            try:
                await self.load_extension(cog)
                log.info(f"  ✓ {cog.split('.')[-1]}")
            except Exception as e:
                log.error(f"  ✗ {cog}: {e}", exc_info=True)

        log.info("Syncing application commands...")
        try:
            await self.tree.sync()
            log.info("✓ Commands synced")
        except Exception as e:
            log.error(f"Failed to sync commands: {e}")

    async def on_ready(self):
        log.info(f"✓ Online as {self.user} (ID: {self.user.id})")
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.playing,
                name="World of Discord | /help"
            )
        )

        # Auto-create game channels in all connected guilds
        for guild in self.guilds:
            try:
                channel_map = await self.channels.setup_guild(guild)
                if channel_map:
                    log.info(f"✓ Game channels ready in {guild.name}: {list(channel_map.keys())}")
                    # Ensure welcome messages exist (won't duplicate if already present)
                    await self.channels.ensure_welcome_messages(guild)
                else:
                    log.warning(f"⚠ Could not create game channels in {guild.name} (missing permissions)")
            except Exception as e:
                log.error(f"✗ Channel setup failed for {guild.name}: {e}")

    def get_game_channel_mention(self, guild_id: int, channel_type: str) -> str:
        """Get a mention string for a game channel, or fallback text."""
        ch_id = self.channels.get_channel_id(guild_id, channel_type)
        if ch_id:
            return f"<#{ch_id}>"
        return f"a dedicated channel"

    async def on_application_command_error(self, interaction: discord.Interaction, error):
        """Handles errors for prefix-style commands (fallback)."""
        await self._handle_error(interaction, error)

    async def _handle_error(self, interaction: discord.Interaction, error):
        from discord import app_commands
        from discord.errors import NotFound, HTTPException

        # Silently ignore expired interactions (Discord 3-second timeout)
        if isinstance(error, (NotFound, app_commands.errors.CommandInvokeError)):
            cause = getattr(error, "original", error)
            if isinstance(cause, NotFound) and cause.code == 10062:
                log.warning(f"Interaction expired (user was too quick or network lag): {interaction.command}")
                return
            # Silently ignore "already acknowledged" (40060) errors
            if isinstance(cause, HTTPException) and cause.code == 40060:
                log.warning(f"Interaction already acknowledged: {interaction.command}")
                return
            # Handle rate limiting (429) gracefully
            if isinstance(cause, HTTPException) and cause.status == 429:
                log.warning(f"Rate limited on command '{getattr(interaction.command, 'name', '?')}' — retrying later")
                return

        log.error(f"Command error in '{getattr(interaction.command, 'name', '?')}': {error}", exc_info=True)
        
        # More specific error messages for common issues
        error_str = str(error).lower()
        if "interaction" in error_str and "expired" in error_str:
            msg = "⏰ Interaction expired. Please try the command again."
        elif "rate limit" in error_str or "429" in error_str:
            msg = "⏳ Rate limited. Please wait a moment and try again."
        elif "not found" in error_str:
            msg = "❌ Command not found. The bot may be restarting."
        else:
            msg = "❌ An unexpected error occurred. Please try again."
        
        try:
            if interaction.response.is_done():
                await interaction.followup.send(f"❌ {msg}", ephemeral=True)
            else:
                await interaction.response.send_message(f"❌ {msg}", ephemeral=True)
        except Exception:
            pass

    async def on_guild_join(self, guild: discord.Guild):
        """Auto-create game channels when bot joins a new server."""
        log.info(f"Joined new guild: {guild.name} (ID: {guild.id})")
        try:
            channel_map = await self.channels.setup_guild(guild)
            if channel_map:
                log.info(f"✓ Game channels created in {guild.name}")
                # Find a general channel to send welcome message
                ch_id = channel_map.get("general")
                if ch_id:
                    ch = guild.get_channel(ch_id)
                    if ch:
                        embed = discord.Embed(
                            title="⚔️ World of Discord",
                            description=(
                                "Game channels have been created!\n\n"
                                f"🎮 **General**: <#{channel_map.get('general', 0)}>\n"
                                f"⚔️ **Combat**: <#{channel_map.get('combat', 0)}>\n"
                                f"🏰 **Dungeons**: <#{channel_map.get('dungeon', 0)}>\n"
                                f"🪙 **Marketplace**: <#{channel_map.get('market', 0)}>\n"
                                f"🗺️ **Exploration**: <#{channel_map.get('explore', 0)}>\n\n"
                                "Type `/help` to get started!"
                            ),
                            color=0xFFD700,
                        )
                        await ch.send(embed=embed)
        except Exception as e:
            log.error(f"Failed to set up channels for {guild.name}: {e}")

    async def close(self):
        log.info("Shutting down...")
        if self.db:
            await self.db.close()
        await super().close()


# ── Entry ──────────────────────────────────────────────────────────────────────

async def main():
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        raise RuntimeError("DISCORD_TOKEN is not set in your .env file.")

    bot = MMORPGBot()
    async with bot:
        await bot.start(token)


if __name__ == "__main__":
    asyncio.run(main())
