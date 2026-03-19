"""
╔══════════════════════════════════════════════════════════════════════════════╗
║     services/channel_manager.py — Auto-create & route game channels         ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import logging
import time
from typing import Dict, Optional

import discord

log = logging.getLogger("channel_manager")

# ── Channel definitions ─────────────────────────────────────────────────────

GAME_CHANNELS = {
    "combat":      {"name": "⚔-combat",       "topic": "Fight enemies here! Use /fight"},
    "dungeon":     {"name": "🏰-dungeons",     "topic": "Dungeon runs here! Use /dungeon enter"},
    "market":      {"name": "🪙-marketplace",  "topic": "Buy & sell items! Use /market"},
    "explore":     {"name": "🗺-exploration",   "topic": "Explore and travel! Use /explore /travel"},
    "quest":       {"name": "📜-quests",        "topic": "NPC Quests & Reputation! Use /interact /quest log /reputation"},
    "announce":    {"name": "📣-announcements","topic": "Server milestones and world announcements"},
    "general":     {"name": "🎮-game-general",  "topic": "General game commands: /character /inventory /help"},
}

CATEGORY_NAME = "🎮 World of Discord"


class ChannelManager:
    """Manages game channel creation and routing."""

    def __init__(self, bot):
        self.bot = bot
        # guild_id -> { channel_type -> channel_id }
        self._cache: Dict[int, Dict[str, int]] = {}

    async def setup_guild(self, guild: discord.Guild) -> Dict[str, int]:
        """Ensure all game channels exist in a guild. Returns channel map."""
        if guild.id in self._cache:
            # Verify channels still exist
            valid = True
            for ctype, ch_id in self._cache[guild.id].items():
                if not guild.get_channel(ch_id):
                    valid = False
                    break
            if valid:
                return self._cache[guild.id]

        # Find or create category
        category = discord.utils.get(guild.categories, name=CATEGORY_NAME)
        if not category:
            try:
                category = await guild.create_category(
                    CATEGORY_NAME,
                    reason="World of Discord game channels"
                )
                log.info(f"Created category '{CATEGORY_NAME}' in {guild.name}")
            except discord.Forbidden:
                log.warning(f"No permission to create category in {guild.name}")
                self._cache[guild.id] = {}
                return {}
            except Exception as e:
                log.error(f"Failed to create category in {guild.name}: {e}")
                self._cache[guild.id] = {}
                return {}

        channel_map = {}
        for ctype, info in GAME_CHANNELS.items():
            # Check if channel already exists
            existing = discord.utils.get(
                guild.text_channels,
                name=info["name"].replace(" ", "-").lower()
            )
            if not existing:
                # Also check by exact name in category
                existing = discord.utils.get(
                    category.text_channels,
                    name=info["name"]
                )
            
            if existing:
                channel_map[ctype] = existing.id
            else:
                try:
                    ch = await guild.create_text_channel(
                        name=info["name"],
                        category=category,
                        topic=info["topic"],
                        reason="World of Discord game channel"
                    )
                    channel_map[ctype] = ch.id
                    log.info(f"Created channel #{info['name']} in {guild.name}")
                except discord.Forbidden:
                    log.warning(f"No permission to create #{info['name']} in {guild.name}")
                except Exception as e:
                    log.error(f"Failed to create #{info['name']}: {e}")

        self._cache[guild.id] = channel_map
        
        # Send welcome messages to new channels
        await self._send_welcome_messages(guild, channel_map)
        
        return channel_map

    async def _should_show_welcome(self, channel: discord.TextChannel, guide_title: str) -> bool:
        """Check if we should show welcome message (if last one is >1 hour old or doesn't exist)."""
        try:
            # Check last 50 messages for a welcome message
            async for msg in channel.history(limit=50):
                if msg.author == channel.guild.me and msg.embeds:
                    for embed in msg.embeds:
                        if embed.title and guide_title in embed.title:
                            # Found welcome message - check if it's recent (within 1 hour)
                            age_seconds = (discord.utils.utcnow() - msg.created_at).total_seconds()
                            if age_seconds < 3600:  # Less than 1 hour old
                                return False
                            # Older than 1 hour, we can show a new one
                            return True
            # No welcome message found
            return True
        except Exception as e:
            log.debug(f"Error checking welcome message in {channel.name}: {e}")
            return False
    
    async def _send_welcome_messages(self, guild: discord.Guild, channel_map: Dict[str, int], force_general: bool = False):
        """Send welcome/help messages to each game channel."""
        import discord
        
        channel_guides = {
            "combat": {
                "title": "⚔️ Combat Channel",
                "description": "Engage in turn-based combat with enemies and bosses!",
                "color": 0xFF4444,
                "commands": [
                    "`/fight [enemy]` — Battle an enemy in your current zone",
                    "`/rest` — Fully recover HP and mana (60s cooldown)",
                ],
                "tips": [
                    "💡 Use `/explore` in the Exploration channel to find enemies",
                    "💡 Bosses give better rewards but are much harder",
                    "💡 Use `/rest` when low on HP/mana",
                ]
            },
            "dungeon": {
                "title": "🏰 Dungeon Channel",
                "description": "Enter challenging dungeons solo or with a party!",
                "color": 0x8B4513,
                "commands": [
                    "`/dungeon list` — Browse available dungeons",
                    "`/dungeon enter [dungeon]` — Enter a solo dungeon",
                    "`/dungeon create [dungeon]` — Create a party dungeon",
                    "`/dungeon invite @player` — Invite someone to your party",
                    "`/dungeon start` — Begin the dungeon (party leader only)",
                    "`/dungeon status` — Check your dungeon progress",
                    "`/dungeon leave` — Leave current dungeon",
                ],
                "tips": [
                    "💡 Dungeons give bonus XP and gold rewards",
                    "💡 Party dungeons allow up to 5 players",
                    "💡 Each dungeon has multiple floors with increasing difficulty",
                ]
            },
            "market": {
                "title": "🪙 Marketplace Channel",
                "description": "Buy and sell items with other players!",
                "color": 0xFFD700,
                "commands": [
                    "`/market browse` — Browse items for sale",
                    "`/market sell [item] [price]` — List an item for sale",
                    "`/market buy [listing]` — Purchase a listing",
                    "`/gold` — Check your gold balance",
                    "`/leaderboard [level|gold]` — View server rankings",
                ],
                "tips": [
                    "💡 There's a small listing fee when selling items",
                    "💡 Listings expire after 7 days",
                    "💡 Use `/inventory` to see your items, `/equipment` to see equipped items",
                ]
            },
            "explore": {
                "title": "🗺️ Exploration Channel",
                "description": "Explore the world, travel between zones, and discover new areas!",
                "color": 0x2F7F3F,
                "commands": [
                    "`/explore` — Explore your current zone (find enemies, loot, or safe paths)",
                    "`/travel [zone]` — Travel to a different zone",
                    "`/map` — View the world map and all available zones",
                ],
                "tips": [
                    "💡 Exploring can find enemies, bosses, or hidden loot",
                    "💡 Each zone has a level requirement",
                    "💡 Use `/fight` in Combat channel after finding an enemy",
                ]
            },
            "general": {
                "title": "🎮 Game General Channel",
                "description": "General game commands and character management!",
                "color": 0x4488FF,
                "commands": [
                    "`/character create` — Create your hero",
                    "`/character profile` — View your stats and gear",
                    "`/character specialize` — Choose your specialization (Lv 10+)",
                    "`/character card` — Generate a visual profile card",
                    "`/inventory` — View your items (clickable grid)",
                    "`/equipment` — View and manage equipped items",
                    "`/equip [item]` — Equip an item",
                    "`/sell [item]` — Sell an item to vendor",
                    "`/shop browse` — View vendor shop",
                    "`/shop buy [item]` — Buy a Health Potion (5🪙)",
                    "`/use [item]` — Use a consumable item",
                    "`/guild create` — Found a guild",
                    "`/guild info` — View guild information",
                    "`/help` — View all commands",
                    "`/achievements` — View your achievements",
                    "`/badges` — Display your earned badges",
                    "`/login` — Claim daily login reward",
                    "`/streak` — View your login streak",
                ],
                "tips": [
                    "💡 Use dedicated channels for combat, dungeons, market, and exploration",
                    "💡 Each channel has its own rate limit to prevent lag",
                    "💡 Check `/help` for a complete command list",
                ]
            },
            "announce": {
                "title": "📣 Announcements Channel",
                "description": "Server milestone unlocks and major world updates appear here.",
                "color": 0xF1C40F,
                "commands": [
                    "`/milestones` — View server milestone progress",
                ],
                "tips": [
                    "💡 Milestone tier unlocks are posted automatically",
                    "💡 Rewards often grant temporary server-wide XP/Gold buffs",
                ]
            },
        }
        
        for ctype, ch_id in channel_map.items():
            if not ch_id:
                continue
                
            channel = guild.get_channel(ch_id)
            if not channel:
                continue
            
            guide = channel_guides.get(ctype)
            if not guide:
                continue
            
            # For general channel, check if we should show (force or old message)
            # For other channels, only show if no welcome exists
            should_show = False
            if ctype == "general" and force_general:
                should_show = await self._should_show_welcome(channel, guide["title"])
            else:
                # Check if channel already has a welcome message (to avoid spam)
                try:
                    has_welcome = False
                    async for msg in channel.history(limit=20):
                        if msg.author == guild.me and msg.embeds:
                            # Check if this embed has the channel's title
                            for embed in msg.embeds:
                                if embed.title and guide["title"] in embed.title:
                                    has_welcome = True
                                    break
                        if has_welcome:
                            break
                    
                    should_show = not has_welcome
                except Exception as e:
                    log.debug(f"Error checking welcome in {channel.name}: {e}")
                    should_show = False
            
            if should_show:
                # No welcome message found, send one
                try:
                    embed = discord.Embed(
                        title=guide["title"],
                        description=guide["description"],
                        color=guide["color"],
                    )
                    
                    embed.add_field(
                        name="📋 Available Commands",
                        value="\n".join(guide["commands"]),
                        inline=False,
                    )
                    
                    if guide.get("tips"):
                        embed.add_field(
                            name="💡 Tips",
                            value="\n".join(guide["tips"]),
                            inline=False,
                        )
                    
                    embed.set_footer(text="World of Discord | Use /help for more info")
                    
                    await channel.send(embed=embed)
                    log.info(f"Sent welcome message to #{channel.name} in {guild.name}")
                except discord.Forbidden:
                    log.warning(f"No permission to send message in #{channel.name}")
                except Exception as e:
                    log.error(f"Failed to send welcome message to #{channel.name}: {e}")

    def get_channel_id(self, guild_id: int, channel_type: str) -> Optional[int]:
        """Get channel ID for a game channel type. Returns None if not set up."""
        return self._cache.get(guild_id, {}).get(channel_type)

    async def get_or_setup(self, guild: discord.Guild, channel_type: str) -> Optional[int]:
        """Get channel ID, setting up if needed."""
        ch_id = self.get_channel_id(guild.id, channel_type)
        if ch_id:
            return ch_id
        channel_map = await self.setup_guild(guild)
        return channel_map.get(channel_type)

    async def ensure_welcome_messages(self, guild: discord.Guild):
        """Ensure all game channels have welcome messages (called on bot startup)."""
        channel_map = self._cache.get(guild.id, {})
        if not channel_map:
            # Channels not set up yet, setup will send messages
            return
        await self._send_welcome_messages(guild, channel_map)
    
    async def maybe_show_general_welcome(self, channel: discord.TextChannel):
        """Check if we should show welcome message in general channel (called on message)."""
        if not channel or not channel.guild:
            return
        
        guild = channel.guild
        channel_map = self._cache.get(guild.id, {})
        if not channel_map:
            return
        
        general_id = channel_map.get("general")
        if general_id and channel.id == general_id:
            # This is the general channel, check if we should show welcome
            await self._send_welcome_messages(guild, { "general": general_id }, force_general=True)


# ── Per-user command cooldown ───────────────────────────────────────────────

class CooldownManager:
    """Simple in-memory per-user command cooldown to prevent rate limit abuse."""

    def __init__(self, default_cooldown: float = 2.0):
        self.default_cooldown = default_cooldown
        # user_id -> last_command_timestamp
        self._last_used: Dict[int, float] = {}

    def check(self, user_id: int, cooldown: float = None) -> Optional[float]:
        """Check if user is on cooldown. Returns remaining seconds, or None if OK."""
        cd = cooldown or self.default_cooldown
        now = time.monotonic()
        last = self._last_used.get(user_id, 0)
        remaining = cd - (now - last)
        if remaining > 0:
            return round(remaining, 1)
        self._last_used[user_id] = now
        return None

    def reset(self, user_id: int):
        """Reset cooldown for a user."""
        self._last_used.pop(user_id, None)


# ── Channel routing helpers ─────────────────────────────────────────────────

# Map command names to their intended channel type
COMMAND_CHANNEL_MAP = {
    # Combat (⚔️ Combat channel)
    "fight": "combat",
    "rest": "combat",
    # Exploration (🗺️ Exploration channel)
    "explore": "explore",
    "travel": "explore",
    "map": "explore",
    # Dungeon (🏰 Dungeons channel)
    "dungeon": "dungeon",
    # Market (🪙 Marketplace channel)
    "market": "market",
    "gold": "market",
    "leaderboard": "market",
    # Quests (📜 Quests channel) - interact can be used in exploration channel too
    "interact": "explore",  # Allow in exploration channel since it sends DMs
    "quest": "quest",
    "reputation": "quest",
    # General (🎮 Game General channel) - All other commands
    "character": "general",
    "inventory": "general",
    "equip": "general",
    "sell": "general",
    "use": "general",
    "shop": "general",
    "guild": "general",
    "help": "general",
    "achievements": "general",
    "badges": "general",
    "login": "general",
    "streak": "general",
    "events": "general",
    "admin": "general",
}


async def check_channel(interaction: discord.Interaction, command_name: str = None) -> bool:
    """
    Check if a command is being used in the correct channel.
    Returns True if OK (correct channel or no channels set up).
    Returns False and BLOCKS the command if wrong channel.
    
    Args:
        command_name: Optional command name override. If not provided, auto-detects from interaction.
    """
    # Auto-detect command name from interaction if not provided
    if not command_name and interaction.command:
        try:
            # Try qualified_name first (works for both groups and regular commands)
            if hasattr(interaction.command, 'qualified_name'):
                full_name = interaction.command.qualified_name
                # For group commands like "character create" or "character.create", get the group name "character"
                # For regular commands like "explore", get "explore"
                if ' ' in full_name:
                    command_name = full_name.split()[0]
                elif '.' in full_name:
                    command_name = full_name.split('.')[0]
                else:
                    command_name = full_name
            # Fallback to name attribute
            elif hasattr(interaction.command, 'name'):
                command_name = interaction.command.name
            # For app_commands.Group, try to get the parent
            elif hasattr(interaction.command, 'parent') and interaction.command.parent:
                if hasattr(interaction.command.parent, 'name'):
                    command_name = interaction.command.parent.name
        except Exception:
            pass
    
    log.debug(f"[CHECK_CHANNEL] Detected command='{command_name}' channel={interaction.channel_id}")
    
    if not command_name:
        return True  # Can't determine command, allow it (better to allow than block)
    
    # Try exact match first
    channel_type = COMMAND_CHANNEL_MAP.get(command_name)
    
    # If not found, try to match group commands (e.g., "character create" -> "character")
    if not channel_type and "." in command_name:
        group_name = command_name.split(".")[0]
        channel_type = COMMAND_CHANNEL_MAP.get(group_name)
    
    # Also check if command_name is a prefix of any mapped command
    if not channel_type:
        for key in COMMAND_CHANNEL_MAP:
            if command_name.startswith(key) or key.startswith(command_name):
                channel_type = COMMAND_CHANNEL_MAP[key]
                break
    
    if not channel_type:
        return True  # No routing rule for this command (allow anywhere)

    bot = interaction.client
    if not hasattr(bot, "channels"):
        return True  # Channel manager not initialized, allow anywhere

    correct_ch_id = bot.channels.get_channel_id(interaction.guild_id, channel_type)
    log.debug(f"[CHECK_CHANNEL] cmd='{command_name}' type='{channel_type}' correct_ch={correct_ch_id} current_ch={interaction.channel_id} match={interaction.channel_id == correct_ch_id}")
    if not correct_ch_id:
        return True  # Channels not set up yet, allow anywhere

    if interaction.channel_id == correct_ch_id:
        return True  # ✅ Correct channel - command allowed

    # ❌ Wrong channel — BLOCK the command and show error
    channel_names = {
        "combat": "⚔️ Combat",
        "dungeon": "🏰 Dungeons",
        "market": "🪙 Marketplace",
        "explore": "🗺️ Exploration",
        "quest": "📜 Quests",
        "general": "🎮 General"
    }
    channel_label = channel_names.get(channel_type, "the correct channel")
    
    try:
        if not interaction.response.is_done():
            await interaction.response.send_message(
                f"❌ **Command blocked!**\n\n"
                f"This command can only be used in {channel_label} channel: <#{correct_ch_id}>\n\n"
                f"**Why?** Each channel has its own rate limit budget, preventing lag and errors.",
                ephemeral=True,
            )
    except Exception:
        pass
    return False  # Block command execution
