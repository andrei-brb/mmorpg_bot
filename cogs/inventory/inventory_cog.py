"""
╔══════════════════════════════════════════════════════════════════════════════╗
║   cogs/inventory/inventory_cog.py — /inventory /equip /sell /use /shop    ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""
import logging
from uuid import UUID
from typing import Optional, List, Dict
import discord
from discord import app_commands
from discord.ext import commands
from config.settings import RARITIES, Settings
from services.character.character_service import CharacterService
from services.character.inventory_service import InventoryService
from services.blacksmith.blacksmith_service import BlacksmithService, ENHANCEMENT_CONFIG, PROTECTION_ITEMS

log = logging.getLogger("cog.inventory")

# Items available in the vendor shop (extend later)
SHOP_ITEM_IDS = ("health_potion",)

# ═══════════════════════════════════════════════════════════════════════════
#  BOX INVENTORY - Grid of clickable slots
# ═══════════════════════════════════════════════════════════════════════════

SLOTS_PER_PAGE = 20  # 4 rows x 5 columns


class SlotButton(discord.ui.Button):
    """One slot in the inventory box. Shows item emoji or empty."""
    
    def __init__(self, slot_index: int, item: Optional[Dict], row: int):
        if item:
            emoji = item.get("icon", "📦")
            label = ""
            style = discord.ButtonStyle.primary if item.get("quantity", 1) > 1 else discord.ButtonStyle.secondary
        else:
            emoji = None
            label = "＋"
            style = discord.ButtonStyle.secondary
        super().__init__(
            style=style,
            emoji=emoji,
            label=label,
            custom_id=f"inv_{slot_index}",
            row=row,
        )
        self.slot_index = slot_index

    async def callback(self, interaction: discord.Interaction):
        view = self.view
        if isinstance(view, BoxInventoryView):
            await view.on_slot_click(interaction, self.slot_index)


class BoxInventoryView(discord.ui.View):
    """Box-style inventory: grid of clickable slots + action buttons."""
    
    def __init__(
        self,
        *,
        owner_id: int,
        char_id: UUID,
        char_name: str,
        gold: int,
        items: List[Dict],
        inv_svc,
        char_svc,
        bs_svc,
        max_slots: int,
    ):
        super().__init__(timeout=300)
        self.owner_id = owner_id
        self.char_id = char_id
        self.char_name = char_name
        self.gold = gold
        self.items = items
        self.inv_svc = inv_svc
        self.char_svc = char_svc
        self.bs_svc = bs_svc
        self.max_slots = max_slots
        self.page = 0
        self.selected_item_id: Optional[str] = None
        self.selected_item: Optional[Dict] = None
        self.equipped_items: Dict[str, Dict] = {}  # slot -> item dict
        
        self._load_equipped()
        self._build_buttons()
    
    def _load_equipped(self):
        """Load currently equipped items."""
        # Get equipped items from the items list
        self.equipped_items = {}
        for item in self.items:
            if item.get("is_equipped") and item.get("equip_slot"):
                self.equipped_items[item["equip_slot"]] = item

    def _build_buttons(self):
        """Build the grid of slot buttons + action row."""
        self.clear_items()
        start = self.page * SLOTS_PER_PAGE
        page_items = self.items[start : start + SLOTS_PER_PAGE]
        
        # Add 20 slot buttons (4 rows x 5 cols)
        for i in range(SLOTS_PER_PAGE):
            item = page_items[i] if i < len(page_items) else None
            row = i // 5
            btn = SlotButton(i, item, row)
            self.add_item(btn)
        
        # Row 4: navigation + primary actions (max 5 buttons)
        prev_btn = discord.ui.Button(emoji="⬅️", style=discord.ButtonStyle.secondary, custom_id="inv_prev", row=4)
        next_btn = discord.ui.Button(emoji="➡️", style=discord.ButtonStyle.secondary, custom_id="inv_next", row=4)
        equip_btn = discord.ui.Button(label="Equip", emoji="⚔️", style=discord.ButtonStyle.primary, custom_id="inv_equip", row=4)
        enhance_btn = discord.ui.Button(label="Enhance", emoji="✨", style=discord.ButtonStyle.primary, custom_id="inv_enhance", row=4)
        sell_btn = discord.ui.Button(label="Sell", emoji="💰", style=discord.ButtonStyle.success, custom_id="inv_sell", row=4)
        
        max_page = max(0, (len(self.items) - 1) // SLOTS_PER_PAGE)
        prev_btn.disabled = self.page <= 0
        next_btn.disabled = self.page >= max_page
        
        has_selection = self.selected_item is not None
        equip_btn.disabled = not has_selection or not (self.selected_item and self.selected_item.get("equip_slot"))
        enhance_btn.disabled = not has_selection or not (self.selected_item and self.selected_item.get("equip_slot"))
        sell_btn.disabled = not has_selection
        
        async def prev_cb(interaction: discord.Interaction):
            if self.page > 0:
                self.page -= 1
                await self._refresh_message(interaction)
        
        async def next_cb(interaction: discord.Interaction):
            if self.page < max_page:
                self.page += 1
                await self._refresh_message(interaction)
        
        prev_btn.callback = prev_cb
        next_btn.callback = next_cb
        equip_btn.callback = self._equip_callback
        enhance_btn.callback = self._enhance_callback
        sell_btn.callback = self._sell_callback
        
        self.add_item(prev_btn)
        self.add_item(next_btn)
        self.add_item(equip_btn)
        self.add_item(enhance_btn)
        self.add_item(sell_btn)
        
        # Add "Use" button as a select menu option or remove it
        # Users can use consumables via /use command if needed

    async def on_slot_click(self, interaction: discord.Interaction, slot_index: int):
        """Handle slot button click - select that item."""
        start = self.page * SLOTS_PER_PAGE
        idx = start + slot_index
        if idx >= len(self.items):
            return await interaction.response.send_message("❌ Empty slot.", ephemeral=True)
        
        item = self.items[idx]
        self.selected_item_id = str(item.get("id"))
        self.selected_item = item
        
        embed = self._build_item_embed(item)
        self._build_buttons()
        
        await interaction.response.edit_message(
            content=f"🎒 **{self.char_name}'s Inventory** ({len(self.items)}/{self.max_slots} slots • {self.gold:,}🪙) • Page {self.page + 1}",
            embed=embed,
            view=self,
        )

    async def _equip_callback(self, interaction: discord.Interaction):
        if not self.selected_item:
            return await interaction.response.send_message("❌ Click a slot to select an item first.", ephemeral=True)
        await interaction.response.defer()
        try:
            item_id = UUID(self.selected_item_id)
        except (ValueError, TypeError):
            return await interaction.followup.send("❌ Invalid item.", ephemeral=True)
        ok, msg = await self.inv_svc.equip(self.char_id, item_id)
        await interaction.followup.send(f"{'✅' if ok else '❌'} {msg}", ephemeral=True)
        await self._reload_and_refresh(interaction)

    async def _sell_callback(self, interaction: discord.Interaction):
        if not self.selected_item:
            return await interaction.response.send_message("❌ Click a slot to select an item first.", ephemeral=True)
        await interaction.response.defer()
        try:
            item_id = UUID(self.selected_item_id)
        except (ValueError, TypeError):
            return await interaction.followup.send("❌ Invalid item.", ephemeral=True)
        ok, msg, gold_gained = await self.inv_svc.sell(self.char_id, item_id)
        if ok:
            self.gold += gold_gained
        await interaction.followup.send(f"{'✅' if ok else '❌'} {msg}", ephemeral=True)
        await self._reload_and_refresh(interaction)

    async def _use_callback(self, interaction: discord.Interaction):
        if not self.selected_item:
            return await interaction.response.send_message("❌ Click a slot to select an item first.", ephemeral=True)
        await interaction.response.defer()
        try:
            item_id = UUID(self.selected_item_id)
        except (ValueError, TypeError):
            return await interaction.followup.send("❌ Invalid item.", ephemeral=True)
        ok, msg, _ = await self.inv_svc.use_consumable(self.char_id, item_id)
        await interaction.followup.send(f"{'✅' if ok else '❌'} {msg}", ephemeral=True)
        await self._reload_and_refresh(interaction)
    
    async def _enhance_callback(self, interaction: discord.Interaction):
        if not self.selected_item:
            return await interaction.response.send_message("❌ Click a slot to select an item first.", ephemeral=True)
        
        # Check if item is equippable (has equip_slot)
        if not self.selected_item.get("equip_slot"):
            return await interaction.response.send_message("❌ Only equippable items can be enhanced.", ephemeral=True)
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            item_id = UUID(self.selected_item_id)
        except (ValueError, TypeError):
            return await interaction.followup.send("❌ Invalid item.", ephemeral=True)
        
        # Get enhancement info
        info = await self.bs_svc.get_enhancement_info(item_id, self.char_id)
        if not info:
            return await interaction.followup.send("❌ Item not found.", ephemeral=True)
        
        if info["current_level"] >= 10:
            return await interaction.followup.send("❌ Item is already at maximum enhancement (+10).", ephemeral=True)
        
        # Get protection inventory
        protections = await self.bs_svc.get_protection_inventory(self.char_id)
        
        # Check if we need protection selection UI
        next_config = ENHANCEMENT_CONFIG.get(info["current_level"] + 1)
        needs_protection = next_config and next_config["can_break"] and (
            protections.get("blessing_scroll", 0) > 0 or
            protections.get("safety_charm", 0) > 0 or
            protections.get("enhancement_fragment", 0) > 0
        )
        
        if needs_protection:
            # Show protection selection UI
            view = EnhancementProtectionView(
                owner_id=self.owner_id,
                char_id=self.char_id,
                item_id=item_id,
                protections=protections,
                target_level=info["current_level"] + 1,
                bs_svc=self.bs_svc,
                inv_svc=self.inv_svc,
                inventory_view=self,
            )
            embed = discord.Embed(
                title="🔨 Select Protection",
                description=f"**{info['item']['name']}** is currently **+{info['current_level']}**\n"
                          f"Enhancing to **+{info['current_level'] + 1}** can break the item!\n\n"
                          f"Choose protection (or select 'None' to proceed without protection):",
                color=0xFFA500
            )
            msg = await interaction.followup.send(embed=embed, view=view, ephemeral=True)
            view.message = msg
        else:
            # Direct enhancement (no protection needed)
            result = await self.bs_svc.enhance_item(
                self.char_id, item_id,
                protection_type=None,
                fragment_count=0
            )
            
            if not result.get("success") and "message" in result:
                return await interaction.followup.send(f"❌ {result['message']}", ephemeral=True)
            
            # Build result embed
            embed = self._build_enhancement_result_embed(result)
            await interaction.followup.send(embed=embed, ephemeral=True)
            
            # Refresh inventory view
            await self._reload_and_refresh(interaction)
            
            # Server announcement for legendary +10
            if result.get("announce"):
                char_row = await self.char_svc.get_by_id(self.char_id)
                if char_row:
                    announce_embed = discord.Embed(
                        title="🌟 LEGENDARY ACHIEVEMENT!",
                        description=f"**{char_row['name']}** has successfully enhanced a **{result.get('item_rarity', 'legendary').title()}** item to **+10**!",
                        color=0xFFD700
                    )
                    try:
                        await interaction.channel.send(embed=announce_embed)
                    except Exception:
                        pass
    
    def _build_enhancement_result_embed(self, result: dict) -> discord.Embed:
        """Build enhancement result embed."""
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
        
        return embed

    async def _refresh_message(self, interaction: discord.Interaction):
        """Refresh the message with current page/selection."""
        self._build_buttons()
        embed = self._build_item_embed(self.selected_item) if self.selected_item else self._build_item_embed(None)
        await interaction.response.edit_message(
            content=f"🎒 **{self.char_name}'s Inventory** ({len(self.items)}/{self.max_slots} slots • {self.gold:,}🪙) • Page {self.page + 1}",
            embed=embed,
            view=self,
        )

    async def _reload_and_refresh(self, interaction: discord.Interaction):
        """Reload inventory from DB and refresh the message."""
        raw_items = await self.inv_svc.get_all(self.char_id)
        char = await self.char_svc.get_by_id(self.char_id)
        if char:
            self.gold = int(char.get("gold", 0))
        formatted = []
        for item in raw_items[:40]:
            formatted.append({
                "id": str(item["id"]),
                "name": item.get("name", "?"),
                "icon": item.get("icon", "📦"),
                "rarity": item.get("rarity", "common"),
                "enhancement_level": item.get("enhancement_level", 0) or 0,
                "quantity": item.get("quantity", 1),
                "item_type": item.get("item_type", ""),
                "equip_slot": item.get("equip_slot"),
                "is_equipped": item.get("is_equipped", False),
                "s_dmg_min": item.get("s_dmg_min"),
                "s_dmg_max": item.get("s_dmg_max"),
                "s_str": item.get("s_str"),
                "s_agi": item.get("s_agi"),
                "s_int": item.get("s_int"),
                "s_armor": item.get("s_armor"),
                "description": item.get("description", ""),
                "level_req": item.get("level_req"),
            })
        self.items = formatted
        self._load_equipped()
        if self.selected_item_id:
            self.selected_item = next((i for i in self.items if str(i.get("id")) == self.selected_item_id), None)
            if not self.selected_item:
                self.selected_item_id = None
        self._build_buttons()
        embed = self._build_item_embed(self.selected_item) if self.selected_item else self._build_item_embed(None)
        await interaction.edit_original_response(
            content=f"🎒 **{self.char_name}'s Inventory** ({len(self.items)}/{self.max_slots} slots • {self.gold:,}🪙) • Page {self.page + 1}",
            embed=embed,
            view=self,
        )

    def _build_item_embed(self, item: Optional[Dict]) -> Optional[discord.Embed]:
        """Build embed showing item details."""
        if not item:
            # Show empty inventory message
            embed = discord.Embed(
                title="🎒 Inventory",
                description="Click a slot to view item details\n\n💡 Use `/equipment` to view equipped items",
                color=0x2F3136,
            )
            return embed
        
        rarity = item.get("rarity", "common")
        rarity_cfg = RARITIES.get(rarity, RARITIES["common"])
        color = rarity_cfg.color
        
        name = item.get("name", "?")
        enh = item.get("enhancement_level", 0) or 0
        if enh > 0:
            name = f"{name} +{enh}"
        
        embed = discord.Embed(
            title=f"{rarity_cfg.emoji} {name}",
            description=item.get("description", "No description."),
            color=color,
        )
        
        # Calculate enhanced stats (base + roll) * enhancement multiplier
        from services.blacksmith.blacksmith_service import ENHANCEMENT_CONFIG
        
        enh_level = item.get("enhancement_level", 0) or 0
        if enh_level > 0:
            enh_config = ENHANCEMENT_CONFIG.get(enh_level, {"stat_boost": 0})
            enh_mult = 1 + enh_config["stat_boost"]
        else:
            enh_mult = 1.0
        
        # Base stats + random rolls
        base_dmg_min = (item.get("s_dmg_min", 0) or 0)
        base_dmg_max = (item.get("s_dmg_max", 0) or 0)
        base_str = (item.get("s_str", 0) or 0) + (item.get("r_str", 0) or 0)
        base_agi = (item.get("s_agi", 0) or 0) + (item.get("r_agi", 0) or 0)
        base_int = (item.get("s_int", 0) or 0) + (item.get("r_int", 0) or 0)
        base_armor = (item.get("s_armor", 0) or 0)
        
        # Apply enhancement multiplier
        final_dmg_min = int(base_dmg_min * enh_mult) if base_dmg_min > 0 else 0
        final_dmg_max = int(base_dmg_max * enh_mult) if base_dmg_max > 0 else 0
        final_str = int(base_str * enh_mult) if base_str > 0 else 0
        final_agi = int(base_agi * enh_mult) if base_agi > 0 else 0
        final_int = int(base_int * enh_mult) if base_int > 0 else 0
        final_armor = int(base_armor * enh_mult) if base_armor > 0 else 0
        
        # Stats
        stats = []
        if final_dmg_min > 0 and final_dmg_max > 0:
            stats.append(f"⚔️ **Damage:** {final_dmg_min}-{final_dmg_max}")
        if final_str > 0:
            stats.append(f"💪 **Str:** +{final_str}")
        if final_agi > 0:
            stats.append(f"⚡ **Agi:** +{final_agi}")
        if final_int > 0:
            stats.append(f"🧠 **Int:** +{final_int}")
        if final_armor > 0:
            stats.append(f"🛡️ **Armor:** +{final_armor}")
        
        if stats:
            embed.add_field(name="📊 Stats", value="\n".join(stats), inline=False)
        
        # Metadata
        meta = []
        meta.append(f"**Type:** {item.get('item_type', '?').title()}")
        if item.get("equip_slot"):
            meta.append(f"**Slot:** {item['equip_slot']}")
        if item.get("quantity", 1) > 1:
            meta.append(f"**Quantity:** {item['quantity']}")
        if item.get("level_req"):
            meta.append(f"**Level Req:** {item['level_req']}")
        
        if meta:
            embed.add_field(name="ℹ️ Info", value="\n".join(meta), inline=False)
        
        embed.set_footer(text=f"Item ID: {item.get('id')}")
        return embed
    
    def _add_equipment_panel(self, embed: discord.Embed):
        """Equipment panel removed - use /equipment command instead."""
        pass

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("❌ This inventory isn't for you.", ephemeral=True)
            return False
        return True


# ═══════════════════════════════════════════════════════════════════════════
#  EQUIPMENT VIEW - Character-shaped equipment slots
# ═══════════════════════════════════════════════════════════════════════════

class EquipmentSlotButton(discord.ui.Button):
    """Equipment slot button in character shape."""
    
    def __init__(self, slot_key: str, slot_label: str, slot_emoji: str, item: Optional[Dict], row: int):
        self.slot_key = slot_key
        if item:
            emoji = item.get("icon", "📦")
            enh = item.get("enhancement_level", 0) or 0
            label = f"{item.get('name', '?')[:12]}" + (f" +{enh}" if enh > 0 else "")
            style = discord.ButtonStyle.primary
        else:
            emoji = slot_emoji
            label = "Empty"
            style = discord.ButtonStyle.secondary
        super().__init__(
            style=style,
            emoji=emoji,
            label=label[:20],  # Discord limit
            custom_id=f"eq_{slot_key}",
            row=row,
        )

    async def callback(self, interaction: discord.Interaction):
        view = self.view
        if isinstance(view, EquipmentView):
            await view.on_equipment_slot_click(interaction, self.slot_key)


class EquipmentView(discord.ui.View):
    """Character equipment display in human shape."""
    
    def __init__(
        self,
        *,
        owner_id: int,
        char_id: UUID,
        char_name: str,
        equipped_items: Dict[str, Dict],
        inv_svc,
        char_svc,
        bs_svc,
    ):
        super().__init__(timeout=300)
        self.owner_id = owner_id
        self.char_id = char_id
        self.char_name = char_name
        self.equipped_items = equipped_items
        self.inv_svc = inv_svc
        self.char_svc = char_svc
        self.bs_svc = bs_svc
        self.selected_slot: Optional[str] = None
        self.message: Optional[discord.Message] = None  # Store message reference
        
        self._build_equipment_buttons()
    
    def _build_equipment_buttons(self):
        """Build character-shaped equipment layout (5 buttons max per row)."""
        self.clear_items()
        
        # Character shape layout (compact):
        # Row 0: [🪖 Head] [📿 Neck] [🥋 Chest] [🧤 Hands] [👖 Legs]
        # Row 1: [👢 Feet] [⚔️ Main] [🛡️ Off] [💍 Ring] [🔮 Trinket]
        
        # Row 0: Head, Neck, Chest, Hands, Legs
        self.add_item(EquipmentSlotButton("head", "Head", "🪖", self.equipped_items.get("head"), row=0))
        self.add_item(EquipmentSlotButton("neck", "Neck", "📿", self.equipped_items.get("neck"), row=0))
        self.add_item(EquipmentSlotButton("chest", "Chest", "🥋", self.equipped_items.get("chest"), row=0))
        self.add_item(EquipmentSlotButton("hands", "Hands", "🧤", self.equipped_items.get("hands"), row=0))
        self.add_item(EquipmentSlotButton("legs", "Legs", "👖", self.equipped_items.get("legs"), row=0))
        
        # Row 1: Feet, Main Hand, Off Hand, Ring, Trinket
        self.add_item(EquipmentSlotButton("feet", "Feet", "👢", self.equipped_items.get("feet"), row=1))
        self.add_item(EquipmentSlotButton("main_hand", "Main", "⚔️", self.equipped_items.get("main_hand"), row=1))
        self.add_item(EquipmentSlotButton("off_hand", "Off", "🛡️", self.equipped_items.get("off_hand"), row=1))
        self.add_item(EquipmentSlotButton("ring", "Ring", "💍", self.equipped_items.get("ring"), row=1))
        self.add_item(EquipmentSlotButton("trinket", "Trinket", "🔮", self.equipped_items.get("trinket"), row=1))
    
    async def on_equipment_slot_click(self, interaction: discord.Interaction, slot_key: str):
        """Handle equipment slot click - show unequip/enhance options."""
        item = self.equipped_items.get(slot_key)
        if not item:
            return await interaction.response.send_message(
                f"❌ **{slot_key.replace('_', ' ').title()}** slot is empty.",
                ephemeral=True
            )
        
        # Show item details with actions
        embed = self._build_item_embed(item)
        view = EquipmentActionView(
            owner_id=self.owner_id,
            char_id=self.char_id,
            slot_key=slot_key,
            item_id=UUID(item["id"]),
            inv_svc=self.inv_svc,
            char_svc=self.char_svc,
            bs_svc=self.bs_svc,
            equipment_view=self,
        )
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    def _build_equipment_embed(self) -> discord.Embed:
        """Build embed showing all equipped items."""
        embed = discord.Embed(
            title=f"👤 {self.char_name}'s Equipment",
            description="Click an equipment slot to manage it",
            color=0x2F3136,
        )
        
        slot_order = [
            ("head", "🪖 Head"),
            ("neck", "📿 Neck"),
            ("chest", "🥋 Chest"),
            ("hands", "🧤 Hands"),
            ("legs", "👖 Legs"),
            ("feet", "👢 Feet"),
            ("main_hand", "⚔️ Main Hand"),
            ("off_hand", "🛡️ Off Hand"),
            ("ring", "💍 Ring"),
            ("trinket", "🔮 Trinket"),
        ]
        
        lines = []
        for slot_key, slot_label in slot_order:
            item = self.equipped_items.get(slot_key)
            if item:
                name = item.get("name", "?")
                enh = item.get("enhancement_level", 0) or 0
                icon = item.get("icon", "📦")
                rarity = item.get("rarity", "common")
                rarity_cfg = RARITIES.get(rarity, RARITIES["common"])
                enh_text = f" +{enh}" if enh > 0 else ""
                lines.append(f"{slot_label}: {rarity_cfg.emoji} {icon} **{name}{enh_text}**")
            else:
                lines.append(f"{slot_label}: `Empty`")
        
        embed.add_field(name="📋 Equipped Items", value="\n".join(lines), inline=False)
        return embed
    
    def _build_item_embed(self, item: Dict) -> discord.Embed:
        """Build embed for a single equipped item."""
        rarity = item.get("rarity", "common")
        rarity_cfg = RARITIES.get(rarity, RARITIES["common"])
        color = rarity_cfg.color
        
        name = item.get("name", "?")
        enh = item.get("enhancement_level", 0) or 0
        if enh > 0:
            name = f"{name} +{enh}"
        
        embed = discord.Embed(
            title=f"{rarity_cfg.emoji} {name}",
            description=item.get("description", "No description."),
            color=color,
        )
        
        # Calculate enhanced stats (base + roll) * enhancement multiplier
        from services.blacksmith.blacksmith_service import ENHANCEMENT_CONFIG
        
        enh_level = item.get("enhancement_level", 0) or 0
        if enh_level > 0:
            enh_config = ENHANCEMENT_CONFIG.get(enh_level, {"stat_boost": 0})
            enh_mult = 1 + enh_config["stat_boost"]
        else:
            enh_mult = 1.0
        
        # Base stats + random rolls
        base_dmg_min = (item.get("s_dmg_min", 0) or 0)
        base_dmg_max = (item.get("s_dmg_max", 0) or 0)
        base_str = (item.get("s_str", 0) or 0) + (item.get("r_str", 0) or 0)
        base_agi = (item.get("s_agi", 0) or 0) + (item.get("r_agi", 0) or 0)
        base_int = (item.get("s_int", 0) or 0) + (item.get("r_int", 0) or 0)
        base_armor = (item.get("s_armor", 0) or 0)
        
        # Apply enhancement multiplier
        final_dmg_min = int(base_dmg_min * enh_mult) if base_dmg_min > 0 else 0
        final_dmg_max = int(base_dmg_max * enh_mult) if base_dmg_max > 0 else 0
        final_str = int(base_str * enh_mult) if base_str > 0 else 0
        final_agi = int(base_agi * enh_mult) if base_agi > 0 else 0
        final_int = int(base_int * enh_mult) if base_int > 0 else 0
        final_armor = int(base_armor * enh_mult) if base_armor > 0 else 0
        
        # Stats
        stats = []
        if final_dmg_min > 0 and final_dmg_max > 0:
            stats.append(f"⚔️ **Damage:** {final_dmg_min}-{final_dmg_max}")
        if final_str > 0:
            stats.append(f"💪 **Str:** +{final_str}")
        if final_agi > 0:
            stats.append(f"⚡ **Agi:** +{final_agi}")
        if final_int > 0:
            stats.append(f"🧠 **Int:** +{final_int}")
        if final_armor > 0:
            stats.append(f"🛡️ **Armor:** +{final_armor}")
        
        if stats:
            embed.add_field(name="📊 Stats", value="\n".join(stats), inline=False)
        
        embed.add_field(
            name="📍 Slot",
            value=f"**{item.get('equip_slot', '?').replace('_', ' ').title()}**",
            inline=False,
        )
        
        embed.set_footer(text=f"Item ID: {item.get('id')}")
        return embed
    
    async def refresh_equipment(self):
        """Reload equipment and refresh view."""
        all_items = await self.inv_svc.get_all(self.char_id)
        equipped_items = {item["equip_slot"]: item for item in all_items if item.get("is_equipped") and item.get("equip_slot")}
        
        formatted_equipped = {}
        for slot, item in equipped_items.items():
            formatted_equipped[slot] = {
                "id": str(item["id"]),
                "name": item.get("name", "?"),
                "icon": item.get("icon", "📦"),
                "rarity": item.get("rarity", "common"),
                "enhancement_level": item.get("enhancement_level", 0) or 0,
                "equip_slot": slot,
                "s_dmg_min": item.get("s_dmg_min"),
                "s_dmg_max": item.get("s_dmg_max"),
                "s_str": item.get("s_str"),
                "s_agi": item.get("s_agi"),
                "s_int": item.get("s_int"),
                "s_armor": item.get("s_armor"),
                "r_str": item.get("r_str", 0) or 0,
                "r_agi": item.get("r_agi", 0) or 0,
                "r_int": item.get("r_int", 0) or 0,
                "description": item.get("description", ""),
                "level_req": item.get("level_req"),
            }
        
        self.equipped_items = formatted_equipped
        self._build_equipment_buttons()
        embed = self._build_equipment_embed()
        
        if self.message:
            try:
                await self.message.edit(
                    content=f"👤 **{self.char_name}'s Equipment**\n\n**💡 Click an equipment slot to manage it!**",
                    embed=embed,
                    view=self,
                )
            except Exception:
                pass
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("❌ This equipment isn't for you.", ephemeral=True)
            return False
        return True


# ═══════════════════════════════════════════════════════════════════════════
#  ENHANCEMENT PROTECTION VIEW - For enhancement with protection selection
# ═══════════════════════════════════════════════════════════════════════════

class EnhancementProtectionView(discord.ui.View):
    """View for selecting protection items during enhancement."""
    
    def __init__(
        self,
        *,
        owner_id: int,
        char_id: UUID,
        item_id: UUID,
        protections: dict,
        target_level: int,
        bs_svc: BlacksmithService,
        inv_svc: InventoryService,
        equipment_view: Optional[EquipmentView] = None,
        inventory_view: Optional[BoxInventoryView] = None,
    ):
        super().__init__(timeout=60)
        self.owner_id = owner_id
        self.char_id = char_id
        self.item_id = item_id
        self.bs_svc = bs_svc
        self.inv_svc = inv_svc
        self.equipment_view = equipment_view
        self.inventory_view = inventory_view
        self.chosen = False
        self.chosen_protection = None
        self.chosen_fragments = 0
        self.has_fragments = protections.get("enhancement_fragment", 0) > 0
        self.message = None
        
        # Add protection select
        self.add_item(_EnhancementProtectionSelect(protections, target_level))
        # Add fragment count select if fragments available
        if self.has_fragments:
            self.add_item(_EnhancementFragmentSelect(protections.get("enhancement_fragment", 0)))
        
        # Add enhance button (initially disabled)
        self.add_item(_EnhancementButton())
    
    def _update_enhance_button(self):
        """Enable enhance button when protection is selected."""
        for item in self.children:
            if isinstance(item, _EnhancementButton):
                item.disabled = (self.chosen_protection is None)
                break
    
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
            await self._consume_protection(self.chosen_protection, self.chosen_fragments)
        
        # Build result embed
        embed = self._build_result_embed(result)
        await interaction.followup.send(embed=embed, ephemeral=True)
        
        # Refresh views
        if self.equipment_view:
            await self.equipment_view.refresh_equipment()
        if self.inventory_view:
            await self.inventory_view._reload_and_refresh(interaction)
        
        # Server announcement for legendary +10
        if result.get("announce"):
            char_row = await self.inv_svc.db.fetchrow(
                "SELECT name FROM characters WHERE id = $1", self.char_id
            )
            if char_row:
                announce_embed = discord.Embed(
                    title="🌟 LEGENDARY ACHIEVEMENT!",
                    description=f"**{char_row['name']}** has successfully enhanced a **{result.get('item_rarity', 'legendary').title()}** item to **+10**!",
                    color=0xFFD700
                )
                try:
                    await interaction.channel.send(embed=announce_embed)
                except Exception:
                    pass
    
    def _build_result_embed(self, result: dict) -> discord.Embed:
        """Build enhancement result embed."""
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
        
        return embed
    
    async def _consume_protection(self, protection_type: Optional[str], fragment_count: int):
        """Consume protection items from inventory after use."""
        # Consume main protection item
        if protection_type in ("blessing_scroll", "safety_charm"):
            items = await self.inv_svc.get_all(self.char_id)
            protection_items = [
                i for i in items
                if i.get("template_id") == f"protection_{protection_type}"
            ]
            if protection_items:
                item = protection_items[0]
                if item.get("quantity", 1) > 1:
                    await self.inv_svc.db.execute(
                        "UPDATE inventory SET quantity = quantity - 1 WHERE id = $1",
                        item["id"]
                    )
                else:
                    await self.inv_svc.db.execute(
                        "DELETE FROM inventory WHERE id = $1",
                        item["id"]
                    )
        
        # Consume fragments
        if fragment_count > 0:
            items = await self.inv_svc.get_all(self.char_id)
            fragment_items = [
                i for i in items
                if i.get("template_id") == "protection_enhancement_fragment"
            ]
            consumed = 0
            for item in fragment_items:
                if consumed >= fragment_count:
                    break
                available = item.get("quantity", 1)
                to_consume = min(available, fragment_count - consumed)
                if to_consume >= available:
                    await self.inv_svc.db.execute(
                        "DELETE FROM inventory WHERE id = $1",
                        item["id"]
                    )
                else:
                    await self.inv_svc.db.execute(
                        "UPDATE inventory SET quantity = quantity - $1 WHERE id = $2",
                        to_consume, item["id"]
                    )
                consumed += to_consume
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("❌ This menu isn't for you.", ephemeral=True)
            return False
        return True


class _EnhancementProtectionSelect(discord.ui.Select):
    """Select protection item for enhancement."""
    
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
        if not isinstance(view, EnhancementProtectionView):
            return await interaction.response.send_message("❌ Internal error.", ephemeral=True)
        
        protection = self.values[0]
        view.chosen_protection = None if protection == "none" else protection
        view._update_enhance_button()
        
        try:
            if not interaction.response.is_done():
                await interaction.response.defer(ephemeral=True)
        except Exception:
            pass
        
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
            if view.message:
                await view.message.edit(embed=embed, view=view)
        except Exception:
            pass


class _EnhancementFragmentSelect(discord.ui.Select):
    """Select fragment count for enhancement."""
    
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
        if not isinstance(view, EnhancementProtectionView):
            return await interaction.response.send_message("❌ Internal error.", ephemeral=True)
        
        view.chosen_fragments = int(self.values[0])
        view._update_enhance_button()
        
        try:
            if not interaction.response.is_done():
                await interaction.response.defer(ephemeral=True)
        except Exception:
            pass
        
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
            if view.message:
                await view.message.edit(embed=embed, view=view)
        except Exception:
            pass


class _EnhancementButton(discord.ui.Button):
    """Button to confirm enhancement."""
    
    def __init__(self):
        super().__init__(
            label="🔨 Enhance Now",
            style=discord.ButtonStyle.primary,
            disabled=True  # Initially disabled
        )
    
    async def callback(self, interaction: discord.Interaction):
        view = self.view
        if not isinstance(view, EnhancementProtectionView):
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
        
        try:
            embed = discord.Embed(
                title="🔨 Enhancing Item...",
                description="Processing your enhancement request...",
                color=0x8B4513
            )
            msg_to_edit = view.message if view.message else interaction.message
            if msg_to_edit:
                await msg_to_edit.edit(embed=embed, view=view)
        except Exception:
            pass
        
        # Perform enhancement
        await view._do_enhancement(interaction)


class EquipmentActionView(discord.ui.View):
    """Actions for an equipped item: Unequip, Enhance, etc."""
    
    def __init__(
        self,
        *,
        owner_id: int,
        char_id: UUID,
        slot_key: str,
        item_id: UUID,
        inv_svc,
        char_svc,
        bs_svc,
        equipment_view: EquipmentView,
    ):
        super().__init__(timeout=60)
        self.owner_id = owner_id
        self.char_id = char_id
        self.slot_key = slot_key
        self.item_id = item_id
        self.inv_svc = inv_svc
        self.char_svc = char_svc
        self.bs_svc = bs_svc
        self.equipment_view = equipment_view
    
    @discord.ui.button(label="🔓 Unequip", style=discord.ButtonStyle.danger, row=0)
    async def unequip_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        ok, msg = await self.inv_svc.unequip_slot(self.char_id, self.slot_key)
        if ok:
            # Refresh equipment view
            await self.equipment_view.refresh_equipment()
            await interaction.followup.send(f"✅ {msg}\n💡 Item moved to inventory. Use `/inventory` to see it.", ephemeral=True)
        else:
            await interaction.followup.send(f"❌ {msg}", ephemeral=True)
    
    @discord.ui.button(label="✨ Enhance", style=discord.ButtonStyle.primary, row=0)
    async def enhance_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        
        # Get enhancement info
        info = await self.bs_svc.get_enhancement_info(self.item_id, self.char_id)
        if not info:
            return await interaction.followup.send("❌ Item not found.", ephemeral=True)
        
        if info["current_level"] >= 10:
            return await interaction.followup.send("❌ Item is already at maximum enhancement (+10).", ephemeral=True)
        
        # Get protection inventory
        protections = await self.bs_svc.get_protection_inventory(self.char_id)
        
        # Check if we need protection selection UI
        next_config = ENHANCEMENT_CONFIG.get(info["current_level"] + 1)
        needs_protection = next_config and next_config["can_break"] and (
            protections.get("blessing_scroll", 0) > 0 or
            protections.get("safety_charm", 0) > 0 or
            protections.get("enhancement_fragment", 0) > 0
        )
        
        if needs_protection:
            # Show protection selection UI
            view = EnhancementProtectionView(
                owner_id=self.owner_id,
                char_id=self.char_id,
                item_id=self.item_id,
                protections=protections,
                target_level=info["current_level"] + 1,
                bs_svc=self.bs_svc,
                inv_svc=self.inv_svc,
                equipment_view=self.equipment_view,
            )
            embed = discord.Embed(
                title="🔨 Select Protection",
                description=f"**{info['item']['name']}** is currently **+{info['current_level']}**\n"
                          f"Enhancing to **+{info['current_level'] + 1}** can break the item!\n\n"
                          f"Choose protection (or select 'None' to proceed without protection):",
                color=0xFFA500
            )
            msg = await interaction.followup.send(embed=embed, view=view, ephemeral=True)
            view.message = msg
        else:
            # Direct enhancement (no protection needed)
            result = await self.bs_svc.enhance_item(
                self.char_id, self.item_id,
                protection_type=None,
                fragment_count=0
            )
            
            if not result.get("success") and "message" in result:
                return await interaction.followup.send(f"❌ {result['message']}", ephemeral=True)
            
            # Build result embed
            embed = self._build_enhancement_result_embed(result)
            await interaction.followup.send(embed=embed, ephemeral=True)
            
            # Refresh equipment view
            await self.equipment_view.refresh_equipment()
            
            # Server announcement for legendary +10
            if result.get("announce"):
                char_row = await self.char_svc.get_by_id(self.char_id)
                if char_row:
                    announce_embed = discord.Embed(
                        title="🌟 LEGENDARY ACHIEVEMENT!",
                        description=f"**{char_row['name']}** has successfully enhanced a **{result.get('item_rarity', 'legendary').title()}** item to **+10**!",
                        color=0xFFD700
                    )
                    try:
                        await interaction.channel.send(embed=announce_embed)
                    except Exception:
                        pass
    
    def _build_enhancement_result_embed(self, result: dict) -> discord.Embed:
        """Build enhancement result embed."""
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
        
        return embed
    
    @discord.ui.button(label="📋 Inspect", style=discord.ButtonStyle.secondary, row=0)
    async def inspect_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Show full item details
        items = await self.inv_svc.get_all(self.char_id)
        item = next((i for i in items if str(i["id"]) == str(self.item_id)), None)
        if not item:
            return await interaction.response.send_message("❌ Item not found.", ephemeral=True)
        
        rarity = RARITIES.get(item.get("rarity", "common"), RARITIES["common"])
        enh_level = item.get("enhancement_level", 0) or 0
        enh_text = f" +{enh_level}" if enh_level > 0 else ""
        
        embed = discord.Embed(
            title=f"{rarity.emoji} {item['name']}{enh_text}",
            description=item.get("description", "No description."),
            color=rarity.color,
        )
        
        # Calculate enhanced stats
        from services.blacksmith.blacksmith_service import ENHANCEMENT_CONFIG
        
        enh_level = item.get("enhancement_level", 0) or 0
        if enh_level > 0:
            enh_config = ENHANCEMENT_CONFIG.get(enh_level, {"stat_boost": 0})
            enh_mult = 1 + enh_config["stat_boost"]
        else:
            enh_mult = 1.0
        
        # Base stats + random rolls
        base_dmg_min = (item.get("s_dmg_min", 0) or 0)
        base_dmg_max = (item.get("s_dmg_max", 0) or 0)
        base_str = (item.get("s_str", 0) or 0) + (item.get("r_str", 0) or 0)
        base_agi = (item.get("s_agi", 0) or 0) + (item.get("r_agi", 0) or 0)
        base_int = (item.get("s_int", 0) or 0) + (item.get("r_int", 0) or 0)
        base_armor = (item.get("s_armor", 0) or 0)
        
        # Apply enhancement multiplier
        final_dmg_min = int(base_dmg_min * enh_mult) if base_dmg_min > 0 else 0
        final_dmg_max = int(base_dmg_max * enh_mult) if base_dmg_max > 0 else 0
        final_str = int(base_str * enh_mult) if base_str > 0 else 0
        final_agi = int(base_agi * enh_mult) if base_agi > 0 else 0
        final_int = int(base_int * enh_mult) if base_int > 0 else 0
        final_armor = int(base_armor * enh_mult) if base_armor > 0 else 0
        
        stats = []
        if final_dmg_min > 0 and final_dmg_max > 0:
            stats.append(f"⚔️ **Damage:** {final_dmg_min}-{final_dmg_max}")
        if final_str > 0:
            stats.append(f"💪 **Str:** +{final_str}")
        if final_agi > 0:
            stats.append(f"⚡ **Agi:** +{final_agi}")
        if final_int > 0:
            stats.append(f"🧠 **Int:** +{final_int}")
        if final_armor > 0:
            stats.append(f"🛡️ **Armor:** +{final_armor}")
        
        if stats:
            embed.add_field(name="📊 Stats", value="\n".join(stats), inline=False)
        
        embed.add_field(
            name="ℹ️ Info",
            value=(
                f"**Slot:** {item.get('equip_slot', '?').replace('_', ' ').title()}\n"
                f"**Rarity:** {item.get('rarity', 'common').title()}\n"
                f"**Level Req:** {item.get('level_req', 1)}"
            ),
            inline=False,
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("❌ This menu isn't for you.", ephemeral=True)
            return False
        return True


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
    def __init__(self, bot): self.bot = bot; self.char_svc = self.inv_svc = self.bs_svc = None
    async def cog_load(self):
        self.char_svc = CharacterService(self.bot.db)
        self.inv_svc  = InventoryService(self.bot.db)
        self.bs_svc   = BlacksmithService(self.bot.db)

    @app_commands.command(name="inventory", description="View your inventory (clickable grid)")
    @app_commands.describe(category="Filter by category (weapon, armor, consumable, material)")
    async def inventory(self, interaction: discord.Interaction, category: Optional[str] = None):
        from services.channel_manager import check_channel
        if not await check_channel(interaction, "inventory"):
            return
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)

        char = await self.char_svc.get_character(interaction.user.id)
        if not char:
            return await interaction.followup.send("❌ No character found.")

        items = await self.inv_svc.get_all(char["id"])
        # Filter out equipped items - they belong in /equipment, not /inventory
        items = [i for i in items if not i.get("is_equipped", False)]
        if category:
            cat = category.lower().strip()
            items = [i for i in items if (i.get("item_type") or "").lower() == cat]

        formatted = []
        for item in items[:40]:
            formatted.append({
                "id": str(item["id"]),
                "name": item.get("name", "?"),
                "icon": item.get("icon", "📦"),
                "rarity": item.get("rarity", "common"),
                "enhancement_level": item.get("enhancement_level", 0) or 0,
                "quantity": item.get("quantity", 1),
                "item_type": item.get("item_type", ""),
                "equip_slot": item.get("equip_slot"),
                "is_equipped": item.get("is_equipped", False),
                "s_dmg_min": item.get("s_dmg_min"),
                "s_dmg_max": item.get("s_dmg_max"),
                "s_str": item.get("s_str"),
                "s_agi": item.get("s_agi"),
                "s_int": item.get("s_int"),
                "s_armor": item.get("s_armor"),
                "description": item.get("description", ""),
                "level_req": item.get("level_req"),
            })

        player = await self.bot.db.fetchrow(
            "SELECT p.is_premium FROM players p JOIN characters c ON c.player_id=p.id WHERE c.id=$1",
            char["id"],
        )
        max_slots = Settings.PREMIUM_INVENTORY_SLOTS if (player and player["is_premium"]) else Settings.FREE_INVENTORY_SLOTS

        # Create box-style inventory view
        view = BoxInventoryView(
            owner_id=interaction.user.id,
            char_id=char["id"],
            char_name=char["name"],
            gold=int(char.get("gold", 0)),
            items=formatted,
            inv_svc=self.inv_svc,
            char_svc=self.char_svc,
            bs_svc=self.bs_svc,
            max_slots=max_slots,
        )

        # Create initial embed
        initial_embed = view._build_item_embed(None)

        await interaction.followup.send(
            content=f"🎒 **{char['name']}'s Inventory** ({len(items)}/{max_slots} slots • {int(char.get('gold', 0)):,}🪙)\n\n**💡 Click a slot to select an item and see details!**\n**💡 Use `/equipment` to view equipped items**",
            embed=initial_embed,
            view=view,
            ephemeral=True,
        )

    @app_commands.command(name="equipment", description="View and manage your equipped items (character shape)")
    async def equipment(self, interaction: discord.Interaction):
        from services.channel_manager import check_channel
        if not await check_channel(interaction, "inventory"):
            return
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)

        char = await self.char_svc.get_character(interaction.user.id)
        if not char:
            return await interaction.followup.send("❌ No character found.")

        # Get only equipped items
        all_items = await self.inv_svc.get_all(char["id"])
        equipped_items = {item["equip_slot"]: item for item in all_items if item.get("is_equipped") and item.get("equip_slot")}

        # Format equipped items
        formatted_equipped = {}
        for slot, item in equipped_items.items():
            formatted_equipped[slot] = {
                "id": str(item["id"]),
                "name": item.get("name", "?"),
                "icon": item.get("icon", "📦"),
                "rarity": item.get("rarity", "common"),
                "enhancement_level": item.get("enhancement_level", 0) or 0,
                "equip_slot": slot,
                "s_dmg_min": item.get("s_dmg_min"),
                "s_dmg_max": item.get("s_dmg_max"),
                "s_str": item.get("s_str"),
                "s_agi": item.get("s_agi"),
                "s_int": item.get("s_int"),
                "s_armor": item.get("s_armor"),
                "r_str": item.get("r_str", 0) or 0,
                "r_agi": item.get("r_agi", 0) or 0,
                "r_int": item.get("r_int", 0) or 0,
                "description": item.get("description", ""),
                "level_req": item.get("level_req"),
            }

        # Create equipment view
        view = EquipmentView(
            owner_id=interaction.user.id,
            char_id=char["id"],
            char_name=char["name"],
            equipped_items=formatted_equipped,
            inv_svc=self.inv_svc,
            char_svc=self.char_svc,
            bs_svc=self.bs_svc,
        )

        embed = view._build_equipment_embed()

        msg = await interaction.followup.send(
            content=f"👤 **{char['name']}'s Equipment**\n\n**💡 Click an equipment slot to manage it!**",
            embed=embed,
            view=view,
            ephemeral=True,
        )
        view.message = msg

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
