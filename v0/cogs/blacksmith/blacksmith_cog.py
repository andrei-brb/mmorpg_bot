"""
╔══════════════════════════════════════════════════════════════════════════════╗
║              cogs/blacksmith/blacksmith_cog.py — Enhancement                 ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""
import logging
from uuid import UUID
from typing import Optional
import discord
from discord import app_commands
from discord.ext import commands
from services.character.character_service import CharacterService
from services.character.inventory_service import InventoryService
from services.blacksmith.blacksmith_service import BlacksmithService, ENHANCEMENT_CONFIG, PROTECTION_ITEMS

log = logging.getLogger("cog.blacksmith")


# ── UI Views ──────────────────────────────────────────────────────────────────

class _ProtectionSelectView(discord.ui.View):
    def __init__(self, *, owner_id: int, char_id: UUID, item_id: UUID, protections: dict, target_level: int, bs_svc: BlacksmithService, inv_svc: InventoryService, cog_instance):
        super().__init__(timeout=60)
        self.owner_id = owner_id
        self.char_id = char_id
        self.item_id = item_id
        self.bs_svc = bs_svc
        self.inv_svc = inv_svc
        self.cog_instance = cog_instance
        self.chosen = False
        self.chosen_protection = None
        self.chosen_fragments = 0
        self.has_fragments = protections.get("enhancement_fragment", 0) > 0
        self.message = None  # Store the message reference
        
        # Add protection select
        self.add_item(_ProtectionSelect(protections, target_level))
        # Add fragment count select if fragments available
        if self.has_fragments:
            self.add_item(_FragmentSelect(protections.get("enhancement_fragment", 0)))
        
        # Add enhance button (initially disabled)
        self.add_item(_EnhanceButton())
    
    def _update_enhance_button(self):
        """Enable enhance button when protection is selected"""
        for item in self.children:
            if isinstance(item, _EnhanceButton):
                # Enable button as soon as protection is selected (protection can be "None")
                # Fragments are optional, so button is enabled even if fragments haven't been selected yet
                item.disabled = (self.chosen_protection is None)
                break
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("❌ This menu isn't for you.", ephemeral=True)
            return False
        return True
    
    async def _do_enhancement(self, interaction: discord.Interaction):
        """Perform the enhancement after protection selection."""
        result = await self.bs_svc.enhance_item(
            self.char_id, self.item_id,
            protection_type=self.chosen_protection,
            fragment_count=self.chosen_fragments
        )
        
        if not result.get("success") and "message" in result:
            await interaction.followup.send(f"❌ {result['message']}", ephemeral=True)
            return
        
        # Consume protection items if used
        if self.chosen_protection or self.chosen_fragments > 0:
            await self.cog_instance._consume_protection(self.char_id, self.chosen_protection, self.chosen_fragments)
        
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
            char_row = await self.cog_instance.bot.db.fetchrow(
                "SELECT name FROM characters WHERE id = $1", self.char_id
            )
            if char_row:
                announce_embed = discord.Embed(
                    title="🌟 LEGENDARY ACHIEVEMENT!",
                    description=f"**{char_row['name']}** has successfully enhanced a **{result.get('item_rarity', 'legendary').title()}** item to **+10**!",
                    color=0xFFD700
                )
                await interaction.channel.send(embed=announce_embed)


class _EnhanceButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label="🔨 Enhance Now",
            style=discord.ButtonStyle.primary,
            disabled=True  # Initially disabled
        )
    
    async def callback(self, interaction: discord.Interaction):
        view = self.view
        if not isinstance(view, _ProtectionSelectView):
            return await interaction.response.send_message("❌ Internal error.", ephemeral=True)
        
        # Disable all items
        for item in view.children:
            if isinstance(item, discord.ui.Select):
                item.disabled = True
        self.disabled = True
        
        view.chosen = True
        view.stop()
        
        try:
            if not interaction.response.is_done():
                await interaction.response.defer(ephemeral=True)
        except Exception:
            pass
        
        # Update message
        try:
            embed = discord.Embed(
                title="🔨 Enhancing Item...",
                description="Processing your enhancement request...",
                color=0x8B4513
            )
            # Try to edit the stored message, or use interaction.message if available
            msg_to_edit = view.message if view.message else interaction.message
            if msg_to_edit:
                await msg_to_edit.edit(embed=embed, view=view)
        except Exception:
            pass
        
        # Perform enhancement
        await view._do_enhancement(interaction)


class _ProtectionSelect(discord.ui.Select):
    def __init__(self, protections: dict, target_level: int):
        options = [
            discord.SelectOption(
                label="None - Proceed without protection",
                value="none",
                description="Risk it! (Item can break on failure)",
                emoji="⚔️"
            )
        ]
        
        # Add blessing scroll if available
        if protections.get("blessing_scroll", 0) > 0:
            options.append(discord.SelectOption(
                label=f"Blessing Scroll (🛡️) x{protections['blessing_scroll']}",
                value="blessing_scroll",
                description="Prevents destruction, downgrades instead",
                emoji="🛡️"
            ))
        
        # Add safety charm if available and level <= 5
        if protections.get("safety_charm", 0) > 0 and target_level <= 5:
            options.append(discord.SelectOption(
                label=f"Safety Charm (✨) x{protections['safety_charm']}",
                value="safety_charm",
                description="Guarantees success (works up to +5)",
                emoji="✨"
            ))
        
        super().__init__(
            placeholder="Choose protection...",
            min_values=1,
            max_values=1,
            options=options
        )
    
    async def callback(self, interaction: discord.Interaction):
        view = self.view
        if not isinstance(view, _ProtectionSelectView):
            return await interaction.response.send_message("❌ Internal error.", ephemeral=True)
        
        protection = self.values[0]
        view.chosen_protection = None if protection == "none" else protection
        
        # Update enhance button state
        view._update_enhance_button()
        
        # Acknowledge selection
        try:
            if not interaction.response.is_done():
                await interaction.response.defer(ephemeral=True)
        except Exception:
            pass
        
        # Update message to show selection
        try:
            protection_name = "None" if protection == "none" else PROTECTION_ITEMS[protection]["name"]
            embed = discord.Embed(
                title="🔨 Select Protection",
                description=(
                    f"**Protection:** {protection_name}\n\n"
                    + ("Select fragments and click **Enhance Now** when ready!" if view.has_fragments else "Click **Enhance Now** to proceed!")
                ),
                color=0xFFA500
            )
            # Try to edit the stored message
            if view.message:
                await view.message.edit(embed=embed, view=view)
        except Exception:
            pass


class _FragmentSelect(discord.ui.Select):
    def __init__(self, fragment_count: int):
        max_fragments = min(fragment_count, 3)  # Can stack up to 3
        options = [
            discord.SelectOption(
                label=f"Use {i} Fragment{'s' if i > 1 else ''} (+{i*10}% success)",
                value=str(i),
                description=f"Adds {i*10}% to success chance",
                emoji="💎"
            )
            for i in range(max_fragments + 1)
        ]
        
        super().__init__(
            placeholder="How many fragments? (Optional)",
            min_values=1,
            max_values=1,
            options=options
        )
    
    async def callback(self, interaction: discord.Interaction):
        view = self.view
        if not isinstance(view, _ProtectionSelectView):
            return await interaction.response.send_message("❌ Internal error.", ephemeral=True)
        
        view.chosen_fragments = int(self.values[0])
        
        # Update enhance button state
        view._update_enhance_button()
        
        try:
            if not interaction.response.is_done():
                await interaction.response.defer(ephemeral=True)
        except Exception:
            pass
        
        # Update message to show fragment selection
        try:
            protection_name = "None" if view.chosen_protection is None else PROTECTION_ITEMS[view.chosen_protection]["name"]
            fragment_text = f"{view.chosen_fragments} fragment{'s' if view.chosen_fragments != 1 else ''}" if view.chosen_fragments > 0 else "No fragments"
            embed = discord.Embed(
                title="🔨 Ready to Enhance",
                description=(
                    f"**Protection:** {protection_name}\n"
                    f"**Fragments:** {fragment_text}\n\n"
                    f"Click **Enhance Now** to proceed!"
                ),
                color=0xFFA500
            )
            # Try to edit the stored message
            if view.message:
                await view.message.edit(embed=embed, view=view)
        except Exception:
            pass


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

    @blacksmith.command(name="enhance", description="Enhance an item (+1 to +10) - Also available in /equipment and /inventory")
    @app_commands.describe(item_id="Item UUID from /inventory")
    async def enhance(self, interaction: discord.Interaction, item_id: str):
        # Channel check removed - enhancement available everywhere via /equipment and /inventory
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        
        char = await self.char_svc.get_character(interaction.user.id)
        if not char:
            return await interaction.followup.send("❌ No character.", ephemeral=True)
        
        try:
            uid = UUID(item_id)
        except ValueError:
            return await interaction.followup.send("❌ Invalid item ID.", ephemeral=True)
        
        # Get item info to check current level
        info = await self.bs_svc.get_enhancement_info(uid, char["id"])
        if not info:
            return await interaction.followup.send("❌ Item not found.", ephemeral=True)
        
        if info["current_level"] >= 10:
            return await interaction.followup.send("❌ Item is already at maximum enhancement (+10).", ephemeral=True)
        
        # Get protection inventory
        protections = await self.bs_svc.get_protection_inventory(char["id"])
        
        # Check if we need protection selection UI
        next_config = ENHANCEMENT_CONFIG.get(info["current_level"] + 1)
        needs_protection_ui = next_config and next_config["can_break"] and (
            protections.get("blessing_scroll", 0) > 0 or
            protections.get("safety_charm", 0) > 0 or
            protections.get("enhancement_fragment", 0) > 0
        )
        
        if needs_protection_ui:
            # Show protection selection UI
            view = _ProtectionSelectView(
                owner_id=interaction.user.id,
                char_id=char["id"],
                item_id=uid,
                protections=protections,
                target_level=info["current_level"] + 1,
                bs_svc=self.bs_svc,
                inv_svc=self.inv_svc,
                cog_instance=self
            )
            embed = discord.Embed(
                title="🔨 Select Protection",
                description=f"**{info['item']['name']}** is currently **+{info['current_level']}**\n"
                          f"Enhancing to **+{info['current_level'] + 1}** can break the item!\n\n"
                          f"Choose protection (or select 'None' to proceed without protection):",
                color=0xFFA500
            )
            msg = await interaction.followup.send(embed=embed, view=view, ephemeral=True)
            view.message = msg  # Store message reference
            await view.wait()
            if not view.chosen:
                return
            # Enhancement is handled by the view
        else:
            # No protection UI needed, proceed directly
            protection_type = None
            fragment_count = 0
            
            # Perform enhancement
            result = await self.bs_svc.enhance_item(
                char["id"], uid,
                protection_type=protection_type,
                fragment_count=fragment_count
            )
            
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

    async def _consume_protection(self, char_id: UUID, protection_type: Optional[str], fragment_count: int):
        """Consume protection items from inventory after use."""
        # Consume main protection item
        if protection_type in ("blessing_scroll", "safety_charm"):
            items = await self.inv_svc.get_all(char_id)
            protection_items = [
                i for i in items
                if i.get("template_id") == f"protection_{protection_type}"
            ]
            if protection_items:
                item = protection_items[0]
                if item.get("quantity", 1) > 1:
                    await self.bot.db.execute(
                        "UPDATE inventory SET quantity = quantity - 1 WHERE id = $1",
                        item["id"]
                    )
                else:
                    await self.bot.db.execute(
                        "DELETE FROM inventory WHERE id = $1",
                        item["id"]
                    )
        
        # Consume enhancement fragments
        if fragment_count > 0:
            items = await self.inv_svc.get_all(char_id)
            fragment_items = [
                i for i in items
                if i.get("template_id") == "protection_enhancement_fragment"
            ]
            consumed = 0
            for item in fragment_items:
                if consumed >= fragment_count:
                    break
                qty = item.get("quantity", 1)
                to_consume = min(fragment_count - consumed, qty)
                if qty > to_consume:
                    await self.bot.db.execute(
                        "UPDATE inventory SET quantity = quantity - $2 WHERE id = $1",
                        item["id"], to_consume
                    )
                else:
                    await self.bot.db.execute(
                        "DELETE FROM inventory WHERE id = $1",
                        item["id"]
                    )
                consumed += to_consume

    @blacksmith.command(name="info", description="View enhancement details for an item")
    @app_commands.describe(item_id="Item UUID from /inventory")
    async def info(self, interaction: discord.Interaction, item_id: str):
        # Channel check removed - available everywhere
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
        # Channel check removed - available everywhere
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
                      f"💰 **{item['cost']:,}**🪙\n"
                      f"`/blacksmith buy {key}`",
                inline=False
            )
        
        embed.set_footer(text="Use /blacksmith buy [item] to purchase")
        await interaction.followup.send(embed=embed, ephemeral=True)

    @blacksmith.command(name="buy", description="Purchase a protection item")
    @app_commands.describe(item="Protection item to buy")
    @app_commands.choices(item=[
        app_commands.Choice(name="Blessing Scroll (🛡️)", value="blessing_scroll"),
        app_commands.Choice(name="Safety Charm (✨)", value="safety_charm"),
        app_commands.Choice(name="Enhancement Fragment (💎)", value="enhancement_fragment"),
    ])
    async def buy(self, interaction: discord.Interaction, item: str):
        # Channel check removed - available everywhere
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        
        char = await self.char_svc.get_character(interaction.user.id)
        if not char:
            return await interaction.followup.send("❌ No character.", ephemeral=True)
        
        ok, msg = await self.bs_svc.buy_protection(char["id"], item)
        
        embed = discord.Embed(
            description=f"{'✅' if ok else '❌'} {msg}",
            color=0x00FF7F if ok else 0xFF0000
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

    @blacksmith.command(name="stats", description="View your enhancement statistics")
    async def stats(self, interaction: discord.Interaction):
        # Channel check removed - available everywhere
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
        # Channel check removed - available everywhere
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
        # Channel check removed - available everywhere
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        
        char = await self.char_svc.get_character(interaction.user.id)
        if not char:
            return await interaction.followup.send("❌ No character.", ephemeral=True)
        
        ok, msg = await self.bs_svc.claim_daily_blessing(char["id"])
        
        if ok:
            # Add the blessing scroll to inventory
            await self.inv_svc.add_item(char["id"], "protection_blessing_scroll", rarity="rare", from_="daily_blessing")
        
        embed = discord.Embed(
            description=f"{'✅' if ok else '❌'} {msg}",
            color=0x00FF7F if ok else 0xFF0000
        )
        await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(BlacksmithCog(bot))
