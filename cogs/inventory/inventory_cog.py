"""
╔══════════════════════════════════════════════════════════════════════════════╗
║        cogs/inventory/inventory_cog.py — /inventory /equip /sell /use      ║
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
            price_each = int(i.get("vendor_sell") or 0)
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
            embed.add_field(
                name="⚔️ Equipped",
                value="\n".join(f"{RARITIES[i['rarity']].emoji} **{i['name']}** *(slot: {i['equip_slot']})*" for i in equipped),
                inline=False,
            )
        if unequipped:
            lines = [f"{RARITIES[i['rarity']].emoji} {i['icon']} **{i['name']}** [{i['rarity'].title()}] x{i['quantity']}\n  `ID: {i['id']}`" for i in unequipped[:12]]
            if len(unequipped) > 12: lines.append(f"*…and {len(unequipped)-12} more*")
            embed.add_field(name="📦 Bag", value="\n".join(lines), inline=False)
        embed.set_footer(text="Use /equip (dropdown)  /sell <id>  /use <id>")
        await interaction.followup.send(embed=embed)

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

            await interaction.response.defer()
        char = await self.char_svc.get_character(interaction.user.id)
        if not char: return await interaction.followup.send("❌ No character.")
        try: uid = UUID(item_id)
        except ValueError: return await interaction.followup.send("❌ Invalid item ID.")
        ok, msg, gold = await self.inv_svc.sell(char["id"], uid)
        if ok: await self.char_svc.add_gold(char["id"], gold, "vendor sale")
        await interaction.followup.send(embed=discord.Embed(description=f"{'✅' if ok else '❌'} {msg}", color=0xFFD700 if ok else 0xFF0000))

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
            if effect["type"] == "heal_hp":
                healed = await self.char_svc.heal(char["id"], effect["value"])
                msg += f" Restored **{healed}** HP."
        await interaction.followup.send(embed=discord.Embed(description=f"{'✅' if ok else '❌'} {msg}", color=0x00FF7F if ok else 0xFF0000))

async def setup(bot): await bot.add_cog(InventoryCog(bot))
