"""
╔══════════════════════════════════════════════════════════════════════════════╗
║   cogs/inventory/inventory_cog.py — /inventory /equip /sell /use /shop    ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""
import logging
from uuid import UUID
from typing import Optional, List
import discord
from discord import app_commands
from discord.ext import commands
from config.settings import RARITIES, Settings
from services.character.character_service import CharacterService
from services.character.inventory_service import InventoryService

log = logging.getLogger("cog.inventory")

# Items available in the vendor shop (extend later)
SHOP_ITEM_IDS = ("health_potion",)

class _EquipSelectView(discord.ui.View):
    def __init__(self, *, owner_id: int, char_id: UUID, inv_svc: InventoryService, items: List[dict]):
        super().__init__(timeout=90)
        self.owner_id = owner_id
        self.char_id = char_id
        self.inv_svc = inv_svc
        self.add_item(_EquipItemSelect(items))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("❌ This menu isn't for you.", ephemeral=True)
            return False
        return True

class _EquipItemSelect(discord.ui.Select):
    def __init__(self, items: List[dict]):
        options: List[discord.SelectOption] = []
        for i in items[:25]:
            rarity = i.get("rarity", "common")
            emoji = getattr(RARITIES.get(rarity), "emoji", "⬜")
            slot = i.get("equip_slot") or "?"
            qty = i.get("quantity", 1)
            label = f"{i.get('name', 'Item')} (x{qty})" if qty > 1 else f"{i.get('name', 'Item')}"
            desc = f"{rarity.title()} • slot: {slot}"
            options.append(
                discord.SelectOption(
                    label=label[:100],
                    description=desc[:100],
                    value=str(i["id"]),
                    emoji=emoji,
                )
            )
        super().__init__(
            placeholder="Choose an item to equip…",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        view = self.view
        if not isinstance(view, _EquipSelectView):
            return await interaction.response.send_message("❌ Internal error.", ephemeral=True)
        if interaction.user.id != view.owner_id:
            return await interaction.response.send_message("❌ This menu isn’t for you.", ephemeral=True)

        if not interaction.response.is_done():

            await interaction.response.defer()
        try:
            uid = UUID(self.values[0])
        except ValueError:
            return await interaction.response.send_message("❌ Invalid item ID.", ephemeral=True)

        ok, msg = await view.inv_svc.equip(view.char_id, uid)
        embed = discord.Embed(
            description=f"{'✅' if ok else '❌'} {msg}",
            color=0x00FF7F if ok else 0xFF0000,
        )
        await interaction.edit_original_response(content=None, embed=embed, view=None)


class _SellSelectView(discord.ui.View):
    def __init__(self, *, owner_id: int, char_id: UUID, inv_svc: InventoryService, char_svc: CharacterService, items: List[dict]):
        super().__init__(timeout=90)
        self.owner_id = owner_id
        self.char_id = char_id
        self.inv_svc = inv_svc
        self.char_svc = char_svc
        self.add_item(_SellItemSelect(items))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("❌ This menu isn't for you.", ephemeral=True)
            return False
        return True

class _SellItemSelect(discord.ui.Select):
    def __init__(self, items: List[dict]):
        options: List[discord.SelectOption] = []
        for i in items[:25]:
            rarity = i.get("rarity", "common")
            emoji = getattr(RARITIES.get(rarity), "emoji", "⬜")
            qty = i.get("quantity", 1)
            # Calculate actual sell value based on rarity
            base_value = int(i.get("vendor_sell") or 0)
            rarity_cfg = RARITIES.get(rarity, RARITIES["common"])
            value_mult = rarity_cfg.value_multiplier
            bonus_stats = (
                (i.get("r_str", 0) or 0) + (i.get("r_agi", 0) or 0) +
                (i.get("r_int", 0) or 0) + (i.get("r_spi", 0) or 0) +
                (i.get("r_sta", 0) or 0) + (i.get("r_haste", 0) or 0) +
                (i.get("r_lifesteal", 0) or 0) + (i.get("r_resistance", 0) or 0) +
                (i.get("r_hit_rating", 0) or 0)
            )
            stat_bonus_mult = 2 if rarity in ("common", "uncommon") else (3 if rarity in ("rare", "epic") else 5)
            price_each = int(base_value * value_mult) + (bonus_stats * stat_bonus_mult)
            label = f"{i.get('name', 'Item')} (x{qty})" if qty > 1 else f"{i.get('name', 'Item')}"
            desc = f"{rarity.title()} • sells: {price_each}🪙 ea"
            options.append(
                discord.SelectOption(
                    label=label[:100],
                    description=desc[:100],
                    value=str(i["id"]),
                    emoji=emoji,
                )
            )
        super().__init__(
            placeholder="Choose an item to sell…",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        view = self.view
        if not isinstance(view, _SellSelectView):
            return await interaction.response.send_message("❌ Internal error.", ephemeral=True)
        if interaction.user.id != view.owner_id:
            return await interaction.response.send_message("❌ This menu isn’t for you.", ephemeral=True)

        if not interaction.response.is_done():

            await interaction.response.defer()
        try:
            uid = UUID(self.values[0])
        except ValueError:
            return await interaction.edit_original_response(content="❌ Invalid item ID.", view=None)

        ok, msg, gold = await view.inv_svc.sell(view.char_id, uid)
        if ok and gold:
            await view.char_svc.add_gold(view.char_id, gold, "vendor sale")

        embed = discord.Embed(
            description=f"{'✅' if ok else '❌'} {msg}",
            color=0xFFD700 if ok else 0xFF0000,
        )
        await interaction.edit_original_response(content=None, embed=embed, view=None)


class InventoryCog(commands.Cog, name="Inventory"):
    def __init__(self, bot): self.bot = bot; self.char_svc = self.inv_svc = None
    async def cog_load(self):
        self.char_svc = CharacterService(self.bot.db)
        self.inv_svc  = InventoryService(self.bot.db)

    @app_commands.command(name="inventory", description="View your inventory")
    async def inventory(self, interaction: discord.Interaction):
        from services.channel_manager import check_channel
        if not await check_channel(interaction, "inventory"):
            return
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        char = await self.char_svc.get_character(interaction.user.id)
        if not char: return await interaction.followup.send("❌ No character.")
        items = await self.inv_svc.get_all(char["id"])
        if not items: return await interaction.followup.send("🎒 Your inventory is empty.")

        embed = discord.Embed(title=f"🎒 {char['name']}'s Inventory", description=f"{len(items)} items", color=0x2F3136)
        equipped = [i for i in items if i["is_equipped"]]
        unequipped = [i for i in items if not i["is_equipped"]]

        if equipped:
            lines = []
            for i in equipped:
                enh_level = i.get("enhancement_level", 0) or 0
                enh_text = f" **+{enh_level}**" if enh_level > 0 else ""
                # Add sparkles for high enhancements
                if enh_level >= 7:
                    enh_text += " ✨✨✨"
                elif enh_level >= 4:
                    enh_text += " ✨✨"
                elif enh_level >= 1:
                    enh_text += " ✨"
                lines.append(f"{RARITIES[i['rarity']].emoji} **{i['name']}{enh_text}** *(slot: {i['equip_slot']})*")
            embed.add_field(
                name="⚔️ Equipped",
                value="\n".join(lines),
                inline=False,
            )
        if unequipped:
            lines = []
            for i in unequipped[:12]:
                enh_level = i.get("enhancement_level", 0) or 0
                enh_text = f" **+{enh_level}**" if enh_level > 0 else ""
                # Add sparkles for high enhancements
                if enh_level >= 7:
                    enh_text += " ✨✨✨"
                elif enh_level >= 4:
                    enh_text += " ✨✨"
                elif enh_level >= 1:
                    enh_text += " ✨"
                lines.append(f"{RARITIES[i['rarity']].emoji} {i['icon']} **{i['name']}{enh_text}** [{i['rarity'].title()}] x{i['quantity']}\n  `ID: {i['id']}`")
            if len(unequipped) > 12: lines.append(f"*…and {len(unequipped)-12} more*")
            embed.add_field(name="📦 Bag", value="\n".join(lines), inline=False)
        embed.set_footer(text="Use /equip (dropdown)  /sell <id>  /use <id>  /inspect <id> to see stats")
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="inspect", description="Inspect an item to see its stats")
    @app_commands.describe(item_id="Item UUID from /inventory")
    async def inspect(self, interaction: discord.Interaction, item_id: str):
        from services.channel_manager import check_channel
        if not await check_channel(interaction, "inventory"):
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
        
        items = await self.inv_svc.get_all(char["id"])
        item = next((i for i in items if i["id"] == uid), None)
        if not item:
            return await interaction.followup.send("❌ Item not found in your inventory.", ephemeral=True)
        
        # Build stats display
        rarity = RARITIES.get(item.get("rarity", "common"), RARITIES["common"])
        enh_level = item.get("enhancement_level", 0) or 0
        enh_text = f" +{enh_level}" if enh_level > 0 else ""
        embed = discord.Embed(
            title=f"{rarity.emoji} {item['name']}{enh_text}",
            description=item.get("description", "No description."),
            color=rarity.color if hasattr(rarity, "color") else 0x808080,
        )
        
        # Item info
        enh_level = item.get("enhancement_level", 0) or 0
        enh_text = f"\n**Enhancement:** +{enh_level}" if enh_level > 0 else ""
        embed.add_field(
            name="📋 Item Info",
            value=(
                f"**Type:** {item.get('item_type', 'unknown').title()}\n"
                f"**Rarity:** {item.get('rarity', 'common').title()}\n"
                f"**Level Req:** {item.get('level_req', 1)}\n"
                f"**Durability:** {item.get('durability', 100)}/100{enh_text}"
            ),
            inline=True,
        )
        
        # Calculate enhanced stats correctly
        enh_level = item.get("enhancement_level", 0) or 0
        from services.blacksmith.blacksmith_service import ENHANCEMENT_CONFIG
        
        # Get enhancement multiplier
        enh_mult = 1.0
        if enh_level > 0:
            enh_config = ENHANCEMENT_CONFIG.get(enh_level, {"stat_boost": 0})
            enh_mult = 1 + enh_config["stat_boost"]
        
        # Calculate final stats: (base + random) * enhancement_multiplier
        def calc_final_stat(base_key: str, roll_key: str = None) -> int:
            base = item.get(base_key, 0) or 0
            roll = (item.get(roll_key, 0) or 0) if roll_key else 0
            total_base = base + roll
            if total_base > 0 and enh_level > 0:
                return int(total_base * enh_mult)
            return total_base
        
        # Primary stats
        stats_lines = []
        final_str = calc_final_stat("s_str", "r_str")
        if final_str > 0:
            base_str = item.get("s_str", 0) or 0
            roll_str = item.get("r_str", 0) or 0
            enh_text = f" ({base_str} base" + (f" + {roll_str} roll" if roll_str > 0 else "") + (f" × {enh_mult:.2f}x enh" if enh_level > 0 else "") + ")" if enh_level > 0 or roll_str > 0 else ""
            stats_lines.append(f"💪 **Strength:** +{final_str}{enh_text}")
        
        final_agi = calc_final_stat("s_agi", "r_agi")
        if final_agi > 0:
            base_agi = item.get("s_agi", 0) or 0
            roll_agi = item.get("r_agi", 0) or 0
            enh_text = f" ({base_agi} base" + (f" + {roll_agi} roll" if roll_agi > 0 else "") + (f" × {enh_mult:.2f}x enh" if enh_level > 0 else "") + ")" if enh_level > 0 or roll_agi > 0 else ""
            stats_lines.append(f"⚡ **Agility:** +{final_agi}{enh_text}")
        
        final_int = calc_final_stat("s_int", "r_int")
        if final_int > 0:
            base_int = item.get("s_int", 0) or 0
            roll_int = item.get("r_int", 0) or 0
            enh_text = f" ({base_int} base" + (f" + {roll_int} roll" if roll_int > 0 else "") + (f" × {enh_mult:.2f}x enh" if enh_level > 0 else "") + ")" if enh_level > 0 or roll_int > 0 else ""
            stats_lines.append(f"🧠 **Intellect:** +{final_int}{enh_text}")
        
        final_spi = calc_final_stat("s_spi", "r_spi")
        if final_spi > 0:
            base_spi = item.get("s_spi", 0) or 0
            roll_spi = item.get("r_spi", 0) or 0
            enh_text = f" ({base_spi} base" + (f" + {roll_spi} roll" if roll_spi > 0 else "") + (f" × {enh_mult:.2f}x enh" if enh_level > 0 else "") + ")" if enh_level > 0 or roll_spi > 0 else ""
            stats_lines.append(f"✨ **Spirit:** +{final_spi}{enh_text}")
        
        final_sta = calc_final_stat("s_sta", "r_sta")
        if final_sta > 0:
            base_sta = item.get("s_sta", 0) or 0
            roll_sta = item.get("r_sta", 0) or 0
            enh_text = f" ({base_sta} base" + (f" + {roll_sta} roll" if roll_sta > 0 else "") + (f" × {enh_mult:.2f}x enh" if enh_level > 0 else "") + ")" if enh_level > 0 or roll_sta > 0 else ""
            stats_lines.append(f"❤️ **Stamina:** +{final_sta}{enh_text}")
        
        final_armor = calc_final_stat("s_armor")
        if final_armor > 0:
            base_armor = item.get("s_armor", 0) or 0
            enh_text = f" ({base_armor} base" + (f" × {enh_mult:.2f}x enh" if enh_level > 0 else "") + ")" if enh_level > 0 else ""
            stats_lines.append(f"🛡️ **Armor:** +{final_armor}{enh_text}")
        
        final_dmg_min = calc_final_stat("s_dmg_min")
        final_dmg_max = calc_final_stat("s_dmg_max")
        if final_dmg_min > 0 or final_dmg_max > 0:
            base_min = item.get("s_dmg_min", 0) or 0
            base_max = item.get("s_dmg_max", 0) or 0
            enh_text = f" ({base_min}-{base_max} base" + (f" × {enh_mult:.2f}x enh" if enh_level > 0 else "") + ")" if enh_level > 0 else ""
            stats_lines.append(f"⚔️ **Damage:** {final_dmg_min}-{final_dmg_max}{enh_text}")
        
        # Secondary stats
        final_haste = calc_final_stat("s_haste", "r_haste")
        if final_haste > 0:
            stats_lines.append(f"⚡ **Haste:** +{final_haste}%")
        final_lifesteal = calc_final_stat("s_lifesteal", "r_lifesteal")
        if final_lifesteal > 0:
            stats_lines.append(f"🩸 **Lifesteal:** +{final_lifesteal}%")
        final_resistance = calc_final_stat("s_resistance", "r_resistance")
        if final_resistance > 0:
            stats_lines.append(f"🛡️ **Resistance:** +{final_resistance}")
        final_hit_rating = calc_final_stat("s_hit_rating", "r_hit_rating")
        if final_hit_rating > 0:
            stats_lines.append(f"🎯 **Hit Rating:** +{final_hit_rating}%")
        
        if stats_lines:
            embed.add_field(name="📊 Stats", value="\n".join(stats_lines), inline=True)
        else:
            embed.add_field(name="📊 Stats", value="*No stats*", inline=True)
        
        # Equip info
        if item.get("equip_slot"):
            status = "✅ Equipped" if item.get("is_equipped") else f"📦 Slot: {item.get('equip_slot', 'unknown')}"
            embed.add_field(name="⚔️ Equipment", value=status, inline=True)
        
        # Value (calculated based on rarity)
        base_value = int(item.get("vendor_sell", 0) or 0)
        if base_value > 0:
            actual_rarity = item.get("rarity", "common")
            rarity_cfg = RARITIES.get(actual_rarity, RARITIES["common"])
            value_mult = rarity_cfg.value_multiplier
            bonus_stats = (
                (item.get("r_str", 0) or 0) + (item.get("r_agi", 0) or 0) +
                (item.get("r_int", 0) or 0) + (item.get("r_spi", 0) or 0) +
                (item.get("r_sta", 0) or 0) + (item.get("r_haste", 0) or 0) +
                (item.get("r_lifesteal", 0) or 0) + (item.get("r_resistance", 0) or 0) +
                (item.get("r_hit_rating", 0) or 0)
            )
            stat_bonus_mult = 2 if actual_rarity in ("common", "uncommon") else (3 if actual_rarity in ("rare", "epic") else 5)
            calculated_value = int(base_value * value_mult) + (bonus_stats * stat_bonus_mult)
            embed.add_field(
                name="💰 Vendor Value",
                value=f"**{calculated_value}**🪙\n(Base: {base_value} × {value_mult:.2f}x + {bonus_stats * stat_bonus_mult} bonus)",
                inline=True
            )
        
        embed.set_footer(text=f"Item ID: {item_id}")
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="equip", description="Equip an item")
    @app_commands.describe(item_id="Item UUID from /inventory (optional)")
    async def equip(self, interaction: discord.Interaction, item_id: Optional[str] = None):
        from services.channel_manager import check_channel
        if not await check_channel(interaction, "equip"):
            return
        # If no ID provided, show a dropdown of equippable items.
        if not item_id:
            if not interaction.response.is_done():
                await interaction.response.defer(ephemeral=True)
            char = await self.char_svc.get_character(interaction.user.id)
            if not char:
                return await interaction.followup.send("❌ No character.", ephemeral=True)
            items = await self.inv_svc.get_all(char["id"])
            equippable = [i for i in items if (i.get("equip_slot") and not i.get("is_equipped"))]
            if not equippable:
                return await interaction.followup.send("❌ You have no equippable items in your bag.", ephemeral=True)

            view = _EquipSelectView(owner_id=interaction.user.id, char_id=char["id"], inv_svc=self.inv_svc, items=equippable)
            extra = "" if len(equippable) <= 25 else f"\n\nShowing **25/{len(equippable)}** items. Use `/inventory` to see all IDs."
            return await interaction.followup.send(f"Select an item to equip:{extra}", view=view, ephemeral=True)

        if not interaction.response.is_done():

            await interaction.response.defer()
        char = await self.char_svc.get_character(interaction.user.id)
        if not char: return await interaction.followup.send("❌ No character.")
        try: uid = UUID(item_id)
        except ValueError: return await interaction.followup.send("❌ Invalid item ID.")
        ok, msg = await self.inv_svc.equip(char["id"], uid)
        await interaction.followup.send(embed=discord.Embed(description=f"{'✅' if ok else '❌'} {msg}", color=0x00FF7F if ok else 0xFF0000))

    @equip.autocomplete("item_id")
    async def equip_autocomplete(self, interaction: discord.Interaction, current: str):
        """Suggest equippable items by name as you type (shows up to 25)."""
        char = await self.char_svc.get_character(interaction.user.id)
        if not char:
            return []
        items = await self.inv_svc.get_all(char["id"])
        equippable = [i for i in items if i.get("equip_slot") and not i.get("is_equipped")]
        current_l = (current or "").lower()
        filtered = [i for i in equippable if current_l in (i.get("name","").lower()) or current_l in str(i.get("id","")).lower()]
        choices = []
        for i in filtered[:25]:
            rarity = i.get("rarity", "common").title()
            slot = i.get("equip_slot") or "?"
            choices.append(app_commands.Choice(name=f"{i.get('name','Item')} • {rarity} • {slot}", value=str(i["id"])))
        return choices

    @app_commands.command(name="sell", description="Sell an item to the vendor")
    @app_commands.describe(item_id="Item UUID from /inventory (optional)")
    async def sell(self, interaction: discord.Interaction, item_id: Optional[str] = None):
        from services.channel_manager import check_channel
        if not await check_channel(interaction, "sell"):
            return
        if not item_id:
            if not interaction.response.is_done():
                await interaction.response.defer(ephemeral=True)
            char = await self.char_svc.get_character(interaction.user.id)
            if not char:
                return await interaction.followup.send("❌ No character.", ephemeral=True)

            items = await self.inv_svc.get_all(char["id"])
            sellable = [
                i for i in items
                if not i.get("is_equipped")
                and not i.get("locked")
                and not i.get("soulbound")
                and int(i.get("vendor_sell") or 0) > 0
            ]
            if not sellable:
                return await interaction.followup.send("❌ You have no sellable items right now.", ephemeral=True)

            view = _SellSelectView(
                owner_id=interaction.user.id,
                char_id=char["id"],
                inv_svc=self.inv_svc,
                char_svc=self.char_svc,
                items=sellable,
            )
            extra = "" if len(sellable) <= 25 else f"\n\nShowing **25/{len(sellable)}** items. Use `/inventory` to see all IDs."
            return await interaction.followup.send(f"Select an item to sell:{extra}", view=view, ephemeral=True)

        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        
        char = await self.char_svc.get_character(interaction.user.id)
        if not char:
            return await interaction.followup.send("❌ No character.", ephemeral=True)
        
        try:
            uid = UUID(item_id)
        except ValueError:
            return await interaction.followup.send("❌ Invalid item ID.", ephemeral=True)
        
        try:
            ok, msg, gold = await self.inv_svc.sell(char["id"], uid)
            if ok and gold:
                await self.char_svc.add_gold(char["id"], gold, "vendor sale")
            
            embed = discord.Embed(
                description=f"{'✅' if ok else '❌'} {msg}",
                color=0xFFD700 if ok else 0xFF0000
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            log.error(f"Error in sell command: {e}", exc_info=True)
            await interaction.followup.send(f"❌ An error occurred while selling: {str(e)}", ephemeral=True)

    @sell.autocomplete("item_id")
    async def sell_autocomplete(self, interaction: discord.Interaction, current: str):
        char = await self.char_svc.get_character(interaction.user.id)
        if not char:
            return []
        items = await self.inv_svc.get_all(char["id"])
        sellable = [
            i for i in items
            if not i.get("is_equipped")
            and not i.get("locked")
            and not i.get("soulbound")
            and int(i.get("vendor_sell") or 0) > 0
        ]
        current_l = (current or "").lower()
        filtered = [i for i in sellable if current_l in (i.get("name","").lower()) or current_l in str(i.get("id","")).lower()]
        choices = []
        for i in filtered[:25]:
            price_each = int(i.get("vendor_sell") or 0)
            qty = i.get("quantity", 1)
            choices.append(app_commands.Choice(
                name=f"{i.get('name','Item')} • {price_each}🪙 ea • x{qty}",
                value=str(i["id"]),
            ))
        return choices

    @app_commands.command(name="use", description="Use a consumable item")
    @app_commands.describe(item_id="Item UUID from /inventory")
    async def use(self, interaction: discord.Interaction, item_id: str):
        from services.channel_manager import check_channel
        if not await check_channel(interaction, "use"):
            return
        if not interaction.response.is_done():
            await interaction.response.defer()
        char = await self.char_svc.get_character(interaction.user.id)
        if not char: return await interaction.followup.send("❌ No character.")
        try: uid = UUID(item_id)
        except ValueError: return await interaction.followup.send("❌ Invalid item ID.")
        ok, msg, effect = await self.inv_svc.use_consumable(char["id"], uid)
        if ok and effect:
            effect_type = effect.get("type")
            effect_value = effect.get("value", 0)
            effect_duration = effect.get("duration", 0)
            
            if effect_type == "heal_hp":
                heal_val = max(effect_value, char["max_hp"] // 4)  # 25% of max, min 80
                healed = await self.char_svc.heal(char["id"], heal_val)
                msg += f" Restored **{healed}** HP."
            elif effect_type == "boost_sta":
                boost_ok, boost_msg = await self.char_svc.boost_stat(
                    char["id"], "sta", effect_value, effect_duration
                )
                if boost_ok:
                    msg += f" {boost_msg}"
                else:
                    msg = boost_msg
            elif effect_type == "boost_str":
                boost_ok, boost_msg = await self.char_svc.boost_stat(
                    char["id"], "str", effect_value, effect_duration
                )
                if boost_ok:
                    msg += f" {boost_msg}"
                else:
                    msg = boost_msg
            elif effect_type == "boost_agi":
                boost_ok, boost_msg = await self.char_svc.boost_stat(
                    char["id"], "agi", effect_value, effect_duration
                )
                if boost_ok:
                    msg += f" {boost_msg}"
                else:
                    msg = boost_msg
            elif effect_type == "boost_int":
                boost_ok, boost_msg = await self.char_svc.boost_stat(
                    char["id"], "int_", effect_value, effect_duration
                )
                if boost_ok:
                    msg += f" {boost_msg}"
                else:
                    msg = boost_msg
            elif effect_type == "boost_spi":
                boost_ok, boost_msg = await self.char_svc.boost_stat(
                    char["id"], "spi", effect_value, effect_duration
                )
                if boost_ok:
                    msg += f" {boost_msg}"
                else:
                    msg = boost_msg
            elif effect_type == "boost_max_hp":
                boost_ok, boost_msg = await self.char_svc.boost_stat(
                    char["id"], "max_hp", effect_value, effect_duration
                )
                if boost_ok:
                    msg += f" {boost_msg}"
                else:
                    msg = boost_msg
            elif effect_type == "boost_resistance":
                # Resistance is a secondary stat, handled differently
                msg += f" Frost resistance increased by {effect_value} for {effect_duration} minutes."
                # TODO: Implement resistance buff system if needed
        await interaction.followup.send(embed=discord.Embed(description=f"{'✅' if ok else '❌'} {msg}", color=0x00FF7F if ok else 0xFF0000))

    # ── /shop ─────────────────────────────────────────────────────────────────

    shop = app_commands.Group(name="shop", description="Buy items from the vendor")

    @shop.command(name="browse", description="View items for sale")
    async def shop_browse(self, interaction: discord.Interaction):
        from services.channel_manager import check_channel
        if not await check_channel(interaction, "inventory"):
            return
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        rows = await self.bot.db.fetch(
            """SELECT id, name, description, icon, vendor_buy, level_req
               FROM item_templates
               WHERE id = ANY($1::text[]) AND vendor_buy > 0
               ORDER BY vendor_buy""",
            list(SHOP_ITEM_IDS),
        )
        if not rows:
            return await interaction.followup.send("🏪 Shop is empty for now.", ephemeral=True)
        embed = discord.Embed(title="🏪 Vendor Shop", description="Buy items with gold.", color=0xFFD700)
        for r in rows:
            embed.add_field(
                name=f"{r['icon']} **{r['name']}** — {r['vendor_buy']:,}🪙",
                value=f"{r['description']}\n`/shop buy {r['id']}`",
                inline=False,
            )
        embed.set_footer(text="Use /shop buy <item> to purchase")
        await interaction.followup.send(embed=embed, ephemeral=True)

    @shop.command(name="buy", description="Buy an item from the vendor")
    @app_commands.describe(item="Item to buy (e.g. health_potion)")
    async def shop_buy(self, interaction: discord.Interaction, item: str):
        from services.channel_manager import check_channel
        if not await check_channel(interaction, "inventory"):
            return
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        item_id = item.strip().lower().replace(" ", "_")
        if item_id not in SHOP_ITEM_IDS:
            return await interaction.followup.send(
                f"❌ **{item}** is not for sale. Use `/shop browse` to see available items.",
                ephemeral=True,
            )
        tmpl = await self.bot.db.fetchrow(
            "SELECT id, name, icon, vendor_buy, level_req FROM item_templates WHERE id=$1 AND vendor_buy>0",
            item_id,
        )
        if not tmpl:
            return await interaction.followup.send("❌ Item not found or not for sale.", ephemeral=True)
        char = await self.char_svc.get_character(interaction.user.id)
        if not char:
            return await interaction.followup.send("❌ No character.", ephemeral=True)
        if char["level"] < (tmpl["level_req"] or 1):
            return await interaction.followup.send(
                f"❌ Requires level **{tmpl['level_req']}**. You are level {char['level']}.",
                ephemeral=True,
            )
        price = int(tmpl["vendor_buy"])
        if char["gold"] < price:
            return await interaction.followup.send(
                f"❌ Not enough gold. Need **{price:,}**🪙, you have **{char['gold']:,}**🪙.",
                ephemeral=True,
            )
        ok = await self.char_svc.deduct_gold(char["id"], price, "vendor purchase")
        if not ok:
            return await interaction.followup.send("❌ Failed to deduct gold.", ephemeral=True)
        ok, msg = await self.inv_svc.add_item(char["id"], item_id, "common", from_="vendor")
        if not ok:
            await self.char_svc.add_gold(char["id"], price, "vendor refund")
            return await interaction.followup.send(f"❌ {msg}", ephemeral=True)
        await interaction.followup.send(
            embed=discord.Embed(
                title="✅ Purchased!",
                description=f"You bought **{tmpl['icon']} {tmpl['name']}** for **{price:,}**🪙.",
                color=0x00FF7F,
            ),
            ephemeral=True,
        )

    @shop_buy.autocomplete("item")
    async def shop_buy_autocomplete(self, interaction: discord.Interaction, current: str):
        current_l = (current or "").lower()
        rows = await self.bot.db.fetch(
            """SELECT id, name, icon, vendor_buy FROM item_templates
               WHERE id = ANY($1::text[]) AND vendor_buy > 0""",
            list(SHOP_ITEM_IDS),
        )
        choices = []
        for r in rows:
            if current_l in r["id"].lower() or current_l in r["name"].lower():
                choices.append(app_commands.Choice(
                    name=f"{r['icon']} {r['name']} — {r['vendor_buy']}🪙",
                    value=r["id"],
                ))
        return choices[:25]

async def setup(bot): await bot.add_cog(InventoryCog(bot))
