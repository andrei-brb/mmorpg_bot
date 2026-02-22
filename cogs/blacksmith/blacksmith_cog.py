"""
╔══════════════════════════════════════════════════════════════════════════════╗
║              cogs/blacksmith/blacksmith_cog.py — Enhancement                 ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""
import logging
from uuid import UUID
import discord
from discord import app_commands
from discord.ext import commands
from services.character.character_service import CharacterService
from services.character.inventory_service import InventoryService
from services.blacksmith.blacksmith_service import BlacksmithService, ENHANCEMENT_CONFIG, PROTECTION_ITEMS

log = logging.getLogger("cog.blacksmith")


class BlacksmithCog(commands.Cog, name="Blacksmith"):
    def __init__(self, bot):
        self.bot = bot
        self.char_svc: CharacterService = None
        self.inv_svc: InventoryService = None
        self.bs_svc: BlacksmithService = None

    async def cog_load(self):
        self.char_svc = CharacterService(self.bot.db)
        self.inv_svc = InventoryService(self.bot.db)
        self.bs_svc = BlacksmithService(self.bot.db)

    blacksmith = app_commands.Group(name="blacksmith", description="Enhance and upgrade your equipment")

    @blacksmith.command(name="enhance", description="Enhance an item (+1 to +10)")
    @app_commands.describe(item_id="Item UUID from /inventory")
    async def enhance(self, interaction: discord.Interaction, item_id: str):
        from services.channel_manager import check_channel
        if not await check_channel(interaction, "blacksmith"):
            return
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        
        char = await self.char_svc.get_character(interaction.user.id)
        if not char:
            return await interaction.followup.send("❌ No character.", ephemeral=True)
        
        try:
            uid = UUID(item_id)
        except ValueError:
            return await interaction.followup.send("❌ Invalid item ID.", ephemeral=True)
        
        # Get protection inventory
        protections = await self.bs_svc.get_protection_inventory(char["id"])
        
        # For now, simple enhancement without protection selection
        # TODO: Add UI for protection selection
        result = await self.bs_svc.enhance_item(char["id"], uid)
        
        if not result.get("success") and "message" in result:
            return await interaction.followup.send(f"❌ {result['message']}", ephemeral=True)
        
        # Build response embed
        embed = discord.Embed(
            title="🔨 Enhancement Result",
            color=0x00FF7F if result.get("success") else (0xFF0000 if result.get("broke") else 0xFFA500)
        )
        
        if result.get("success"):
            embed.description = f"✨ **SUCCESS!**\n{result['message']}"
            embed.add_field(
                name="📊 Enhancement",
                value=f"**+{result['old_level']}** → **+{result['new_level']}**\n"
                      f"Stat boost: **+{result['stat_boost']*100:.0f}%**",
                inline=True
            )
        elif result.get("broke"):
            embed.description = f"💥 **ENHANCEMENT FAILED!**\n{result['message']}"
            embed.color = 0xFF0000
        elif result.get("downgraded"):
            embed.description = f"🛡️ **Protected!**\n{result['message']}"
            embed.color = 0xFFA500
        else:
            embed.description = f"❌ **Failed**\n{result['message']}"
            embed.color = 0xFFA500
        
        embed.add_field(
            name="💰 Cost",
            value=f"**{result['cost']:,}**🪙",
            inline=True
        )
        
        if result.get("success_rate"):
            embed.add_field(
                name="🎲 Success Rate",
                value=f"**{result['success_rate']:.1f}%**",
                inline=True
            )
        
        await interaction.followup.send(embed=embed, ephemeral=True)
        
        # Server announcement for legendary +10
        if result.get("announce"):
            announce_embed = discord.Embed(
                title="🌟 LEGENDARY ACHIEVEMENT!",
                description=f"**{char['name']}** has successfully enhanced a **{result.get('item_rarity', 'legendary').title()}** item to **+10**!",
                color=0xFFD700
            )
            await interaction.channel.send(embed=announce_embed)

    @blacksmith.command(name="info", description="View enhancement details for an item")
    @app_commands.describe(item_id="Item UUID from /inventory")
    async def info(self, interaction: discord.Interaction, item_id: str):
        from services.channel_manager import check_channel
        if not await check_channel(interaction, "blacksmith"):
            return
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        
        char = await self.char_svc.get_character(interaction.user.id)
        if not char:
            return await interaction.followup.send("❌ No character.", ephemeral=True)
        
        try:
            uid = UUID(item_id)
        except ValueError:
            return await interaction.followup.send("❌ Invalid item ID.", ephemeral=True)
        
        info = await self.bs_svc.get_enhancement_info(uid, char["id"])
        if not info:
            return await interaction.followup.send("❌ Item not found.", ephemeral=True)
        
        item = info["item"]
        embed = discord.Embed(
            title=f"🔨 {item['name']} Enhancement Info",
            color=0x8B4513
        )
        
        embed.add_field(
            name="📊 Current Enhancement",
            value=f"**+{info['current_level']}**" + (" (MAX)" if info['current_level'] >= 10 else ""),
            inline=True
        )
        
        if info.get("next_config"):
            embed.add_field(
                name="⬆️ Next Level",
                value=f"**+{info['next_level']}**\n"
                      f"Cost: **{info['next_config']['cost']:,}**🪙\n"
                      f"Success: **{info['next_config']['success_rate']*100:.0f}%**",
                inline=True
            )
            
            if info['next_config']['can_break']:
                embed.add_field(
                    name="⚠️ Warning",
                    value="**Can break on failure!**\nUse protection items!",
                    inline=True
                )
        
        # Show stat comparison
        if info.get("next_stats"):
            stats_lines = []
            for stat in ["str", "agi", "int", "spi", "sta", "armor"]:
                current = info['current_stats'].get(stat, 0)
                next_val = info['next_stats'].get(stat, 0)
                if current > 0 or next_val > 0:
                    stat_name = stat.upper() if stat != "int" else "INT"
                    stats_lines.append(f"**{stat_name}:** {current} → {next_val} (+{next_val - current})")
            
            if stats_lines:
                embed.add_field(
                    name="📈 Stat Preview",
                    value="\n".join(stats_lines[:6]),
                    inline=False
                )
        
        await interaction.followup.send(embed=embed, ephemeral=True)

    @blacksmith.command(name="shop", description="Buy protection items")
    async def shop(self, interaction: discord.Interaction):
        from services.channel_manager import check_channel
        if not await check_channel(interaction, "blacksmith"):
            return
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        
        embed = discord.Embed(
            title="🛒 Blacksmith Shop — Protection Items",
            description="Protect your items during enhancement!",
            color=0xFFD700
        )
        
        for key, item in PROTECTION_ITEMS.items():
            embed.add_field(
                name=f"{item['emoji']} {item['name']}",
                value=f"{item['description']}\n"
                      f"💰 **{item['cost']:,}**🪙",
                inline=False
            )
        
        embed.set_footer(text="Use /blacksmith buy [item] to purchase (coming soon)")
        await interaction.followup.send(embed=embed, ephemeral=True)

    @blacksmith.command(name="stats", description="View your enhancement statistics")
    async def stats(self, interaction: discord.Interaction):
        from services.channel_manager import check_channel
        if not await check_channel(interaction, "blacksmith"):
            return
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        
        char = await self.char_svc.get_character(interaction.user.id)
        if not char:
            return await interaction.followup.send("❌ No character.", ephemeral=True)
        
        stats = await self.bs_svc.get_player_stats(char["id"])
        
        embed = discord.Embed(
            title=f"📊 {char['name']}'s Enhancement Stats",
            color=0x8B4513
        )
        
        embed.add_field(
            name="✅ Successes",
            value=f"**{stats.get('successes', 0)}**",
            inline=True
        )
        embed.add_field(
            name="❌ Failures",
            value=f"**{stats.get('failures', 0)}**",
            inline=True
        )
        embed.add_field(
            name="💔 Downgrades",
            value=f"**{stats.get('downgrades', 0)}**",
            inline=True
        )
        embed.add_field(
            name="💰 Gold Spent",
            value=f"**{stats.get('total_gold_spent', 0):,}**🪙",
            inline=True
        )
        embed.add_field(
            name="⭐ Highest Enhancement",
            value=f"**+{stats.get('highest_enhancement', 0)}**",
            inline=True
        )
        
        await interaction.followup.send(embed=embed, ephemeral=True)

    @blacksmith.command(name="leaderboard", description="Top enhanced items on the server")
    async def leaderboard(self, interaction: discord.Interaction):
        from services.channel_manager import check_channel
        if not await check_channel(interaction, "blacksmith"):
            return
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        
        items = await self.bs_svc.get_leaderboard(10)
        
        if not items:
            return await interaction.followup.send("❌ No enhanced items found yet.", ephemeral=True)
        
        embed = discord.Embed(
            title="🏆 Enhancement Leaderboard",
            description="Top enhanced items on the server",
            color=0xFFD700
        )
        
        lines = []
        for i, item in enumerate(items, 1):
            rarity_emoji = {"common": "⬜", "uncommon": "🟩", "rare": "🟦", "epic": "🟪", "legendary": "🟧", "artifact": "🔶"}.get(item.get("rarity", "common"), "⬜")
            lines.append(f"**{i}.** {item.get('icon', '📦')} **{item['item_name']}** +{item['enhancement_level']} — *{item['char_name']}* {rarity_emoji}")
        
        embed.description = "\n".join(lines)
        await interaction.followup.send(embed=embed, ephemeral=True)

    @blacksmith.command(name="blessing", description="Claim your daily free Blessing Scroll")
    async def blessing(self, interaction: discord.Interaction):
        from services.channel_manager import check_channel
        if not await check_channel(interaction, "blacksmith"):
            return
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        
        char = await self.char_svc.get_character(interaction.user.id)
        if not char:
            return await interaction.followup.send("❌ No character.", ephemeral=True)
        
        ok, msg = await self.bs_svc.claim_daily_blessing(char["id"])
        
        embed = discord.Embed(
            description=f"{'✅' if ok else '❌'} {msg}",
            color=0x00FF7F if ok else 0xFF0000
        )
        await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(BlacksmithCog(bot))
