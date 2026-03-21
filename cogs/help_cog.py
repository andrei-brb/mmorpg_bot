"""
╔══════════════════════════════════════════════════════════════════════════════╗
║              cogs/help_cog.py — /help command                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""
import discord
from discord import app_commands
from discord.ext import commands
from config.settings import Settings


class HelpCog(commands.Cog, name="Help"):
    def __init__(self, bot): self.bot = bot

    @app_commands.command(name="help", description="View all commands and game info")
    async def help(self, interaction: discord.Interaction):
        from services.channel_manager import check_channel
        if not await check_channel(interaction, "help"):
            return
        embed = discord.Embed(
            title=f"📖 {Settings.BOT_NAME} — Command Guide",
            description="A WoW-inspired MMORPG. Build your hero. Conquer the world.",
            color=0x2F7F3F,
        )
        embed.add_field(
            name="⚔️ Character",
            value=(
                "`/character create` — Create your hero\n"
                "`/character profile` — View stats and gear\n"
                "`/character specialize` — Choose your spec (Lv 10)\n"
                "`/character classes` — Browse all classes\n"
                "`/character delete` — Delete your character"
            ),
            inline=False,
        )
        embed.add_field(
            name="🗺️ Exploration",
            value=(
                "`/explore` — Explore your current zone\n"
                "`/travel <zone>` — Travel to a new zone\n"
                "`/map` — View the world map"
            ),
            inline=False,
        )
        embed.add_field(
            name="⚔️ Combat",
            value=(
                "`/fight [enemy]` — Battle an enemy\n"
                "`/rest` — Recover HP and mana (60s cooldown)"
            ),
            inline=False,
        )
        embed.add_field(
            name="🎒 Inventory",
            value=(
                "`/inventory` — View your items (clickable grid, excludes equipped)\n"
                "`/equipment` — View and manage equipped items (character shape)\n"
                "`/equip` — Equip an item (dropdown)\n"
                "`/equip <id>` — Equip by item ID\n"
                "`/sell <id>` — Sell an item to vendor\n"
                "`/use <id>` — Use a consumable"
            ),
            inline=False,
        )
        embed.add_field(
            name="🏪 Shop",
            value=(
                "`/shop browse` — View items for sale\n"
                "`/shop buy <item>` — Buy a Health Potion (5🪙)"
            ),
            inline=False,
        )
        embed.add_field(
            name="🏰 Guild",
            value=(
                "`/guild create` — Found a guild\n"
                "`/guild info [name]` — View guild info\n"
                "`/guild leave` — Leave your guild\n"
                "`/guild disband` — Disband (guildmaster only)"
            ),
            inline=False,
        )
        embed.add_field(
            name="💰 Economy",
            value=(
                "`/gold` — Check your balance\n"
                "`/market browse` — Browse the marketplace\n"
                "`/market sell <id> <price>` — List an item for sale\n"
                "`/market buy <listing_id>` — Purchase a listing\n"
                "`/leaderboard [level|gold]` — Server rankings"
            ),
            inline=False,
        )
        embed.add_field(
            name="📅 Events",
            value=(
                "`/events` — View active world events\n"
                "`/daily` — View your daily quest"
            ),
            inline=False,
        )
        embed.add_field(
            name="🏰 Dungeons",
            value=(
                "`/dungeon list` — Browse available dungeons\n"
                "`/dungeon enter` — Enter a solo dungeon\n"
                "`/dungeon create` — Create a party dungeon\n"
                "`/dungeon invite @player` — Invite to your party\n"
                "`/dungeon start` — Begin the dungeon run\n"
                "`/dungeon status` — Check dungeon progress\n"
                "`/dungeon leave` — Leave current dungeon"
            ),
            inline=False,
        )
        embed.add_field(
            name="🏆 Achievements",
            value=(
                "`/achievements` — View your achievements\n"
                "`/badges` — Display your earned badges"
            ),
            inline=False,
        )
        embed.add_field(
            name="📅 Daily",
            value=(
                "`/login` — Claim daily login reward\n"
                "`/streak` — View your login streak"
            ),
            inline=False,
        )
        embed.add_field(
            name="🖥️ Visual client (Activity)",
            value=(
                "`/open_game` — Open the embedded game UI (Activity) inside Discord\n"
                "`/activity` — Setup notes if `/open_game` doesn’t work"
            ),
            inline=False,
        )
        embed.add_field(
            name="⚙️ Admin",
            value="`/admin help` — View admin-only commands",
            inline=False,
        )

        # Show channel hints if available
        if interaction.guild:
            ch_mgr = getattr(self.bot, "channels", None)
            if ch_mgr:
                ch_map = ch_mgr._cache.get(interaction.guild_id, {})
                if ch_map:
                    lines = []
                    labels = {"combat": "⚔️ Combat", "dungeon": "🏰 Dungeons",
                              "market": "🪙 Market", "explore": "🗺️ Exploration",
                              "general": "🎮 General"}
                    for ctype, label in labels.items():
                        ch_id = ch_map.get(ctype)
                        if ch_id:
                            lines.append(f"{label}: <#{ch_id}>")
                    if lines:
                        embed.add_field(
                            name="📍 Game Channels",
                            value="\n".join(lines),
                            inline=False,
                        )

        embed.set_footer(text=f"World of Discord v{Settings.VERSION} | Conquer your destiny")
        await interaction.response.send_message(embed=embed)


async def setup(bot): await bot.add_cog(HelpCog(bot))
