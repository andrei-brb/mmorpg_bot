"""
╔══════════════════════════════════════════════════════════════════════════════╗
║         BOX INVENTORY - Click slots like a game inventory grid               ║
╚══════════════════════════════════════════════════════════════════════════════╝

Box-style inventory: grid of clickable slots. Click a slot to select, see details.
Command: /inventory_grid [category]
"""

import io
import logging
from typing import List, Dict, Optional
from uuid import UUID

import discord
from discord import app_commands
from discord.ext import commands
from PIL import Image, ImageDraw, ImageFont

from config.settings import Settings, RARITIES

log = logging.getLogger("visual_inventory")


# ═══════════════════════════════════════════════════════════════════════════
#  FONT LOADING (cross-platform)
# ═══════════════════════════════════════════════════════════════════════════

def _load_fonts():
    """Load fonts with fallbacks for Linux, macOS, Windows."""
    default = ImageFont.load_default()
    bold_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "C:/Windows/Fonts/arialbd.ttf",
    ]
    reg_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/TTF/DejaVuSans.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "C:/Windows/Fonts/arial.ttf",
    ]
    bold = default
    for p in bold_paths:
        try:
            bold = ImageFont.truetype(p, 32)
            break
        except (OSError, TypeError):
            pass
    reg = default
    for p in reg_paths:
        try:
            reg = ImageFont.truetype(p, 18)
            break
        except (OSError, TypeError):
            pass
    return {"bold": bold, "regular": reg}


# ═══════════════════════════════════════════════════════════════════════════
#  VISUAL INVENTORY GENERATOR
# ═══════════════════════════════════════════════════════════════════════════

class VisualInventoryGenerator:
    """Generates beautiful inventory grid images."""

    COLORS = {
        "bg_dark": "#1E1F22",
        "bg_mid": "#2B2D31",
        "bg_light": "#313338",
        "text_light": "#DCDDDE",
        "text_gray": "#B5BAC1",
        "text_dark": "#80848E",
        "border": "#40444B",
        "legendary": "#FF8C00",
        "artifact": "#E6CC80",
        "epic": "#9B59B6",
        "rare": "#5865F2",
        "uncommon": "#57F287",
        "common": "#B5BAC1",
        "orange": "#FF8C00",
        "blue": "#5865F2",
        "green": "#57F287",
        "red": "#ED4245",
        "purple": "#9B59B6",
        "gold": "#FEE75C",
    }

    def __init__(self):
        f = _load_fonts()
        self.font_title = f.get("bold", ImageFont.load_default())
        self.font_header = f.get("bold", ImageFont.load_default())
        self.font_body = f.get("regular", ImageFont.load_default())
        self.font_small = f.get("regular", ImageFont.load_default())
        self.font_tiny = f.get("regular", ImageFont.load_default())
        self.font_icon = f.get("bold", ImageFont.load_default())
        self.font_icon_large = f.get("bold", ImageFont.load_default())

    def generate_inventory_image(
        self,
        items: List[Dict],
        character_name: str,
        gold: int,
        max_slots: int = 20,
        selected_item_id: Optional[str] = None,
    ) -> io.BytesIO:
        width, height = 1000, 1200
        img = Image.new("RGB", (width, height), color=self.COLORS["bg_mid"])
        draw = ImageDraw.Draw(img)

        # Top bar
        draw.rectangle([20, 20, 980, 100], fill=self.COLORS["bg_dark"])
        draw.text((40, 40), f"🎒 {character_name}'s Inventory", fill=self.COLORS["orange"], font=self.font_title)
        draw.text((40, 75), f"{len(items)} / {max_slots} slots • {gold:,}🪙", fill=self.COLORS["text_gray"], font=self.font_small)

        # Grid
        grid_y = 140
        cell_size = 90
        gap = 10
        cols = 10
        rows = 4
        for idx in range(cols * rows):
            row, col = idx // cols, idx % cols
            x = 30 + col * (cell_size + gap)
            y = grid_y + row * (cell_size + gap)
            if idx < len(items):
                item = items[idx]
                is_selected = selected_item_id and str(item.get("id")) == selected_item_id
                self._draw_item_cell(draw, item, x, y, cell_size, is_selected)
            else:
                self._draw_empty_cell(draw, x, y, cell_size)

        output = io.BytesIO()
        img.save(output, format="PNG")
        output.seek(0)
        return output

    def _draw_item_cell(self, draw, item: Dict, x: int, y: int, size: int, is_selected: bool = False):
        draw.rounded_rectangle([x, y, x + size, y + size], radius=8, fill=self.COLORS["bg_light"])
        rarity = item.get("rarity", "common")
        rarity_color = self.COLORS.get(rarity, self.COLORS["common"])
        border_width = 5 if is_selected else 3
        draw.rounded_rectangle([x - 1, y - 1, x + size + 1, y + size + 1], radius=8, outline=rarity_color, width=border_width)
        icon = item.get("icon", "📦")
        draw.text((x + size // 2 - 18, y + 15), icon, fill=self.COLORS["text_light"], font=self.font_icon)
        enh = item.get("enhancement_level", 0) or 0
        if enh > 0:
            draw.rounded_rectangle([x + size - 32, y + 5, x + size - 5, y + 25], radius=4, fill=self.COLORS["bg_dark"])
            draw.text((x + size - 28, y + 6), f"+{enh}", fill=self.COLORS["orange"], font=self.font_tiny)
        qty = item.get("quantity", 1)
        if qty > 1:
            draw.rounded_rectangle([x + size - 45, y + size - 25, x + size - 5, y + size - 5], radius=4, fill=self.COLORS["bg_dark"])
            draw.text((x + size - 41, y + size - 22), f"x{qty}", fill=self.COLORS["text_light"], font=self.font_tiny)
        name = (item.get("name", "?")[:8] + "..") if len(item.get("name", "")) > 10 else item.get("name", "?")
        draw.text((x + 5, y + size - 22), name, fill=self.COLORS["text_gray"], font=self.font_tiny)

    def _draw_empty_cell(self, draw, x: int, y: int, size: int):
        draw.rounded_rectangle([x, y, x + size, y + size], radius=8, fill=self.COLORS["bg_dark"], outline=self.COLORS["border"], width=2)
        draw.text((x + size // 2 - 10, y + size // 2 - 10), "＋", fill=self.COLORS["border"], font=self.font_header)


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
        generator: Optional[VisualInventoryGenerator],
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
        self.generator = generator
        self.max_slots = max_slots
        self.page = 0
        self.selected_item_id: Optional[str] = None
        self.selected_item: Optional[Dict] = None
        
        self._build_buttons()

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
        
        # Row 4: navigation + actions
        prev_btn = discord.ui.Button(emoji="⬅️", style=discord.ButtonStyle.secondary, custom_id="inv_prev", row=4)
        next_btn = discord.ui.Button(emoji="➡️", style=discord.ButtonStyle.secondary, custom_id="inv_next", row=4)
        equip_btn = discord.ui.Button(label="Equip", emoji="⚔️", style=discord.ButtonStyle.primary, custom_id="inv_equip", row=4)
        sell_btn = discord.ui.Button(label="Sell", emoji="💰", style=discord.ButtonStyle.success, custom_id="inv_sell", row=4)
        use_btn = discord.ui.Button(label="Use", emoji="🧪", style=discord.ButtonStyle.secondary, custom_id="inv_use", row=4)
        
        max_page = max(0, (len(self.items) - 1) // SLOTS_PER_PAGE)
        prev_btn.disabled = self.page <= 0
        next_btn.disabled = self.page >= max_page
        
        has_selection = self.selected_item is not None
        equip_btn.disabled = not has_selection or not (self.selected_item and self.selected_item.get("equip_slot"))
        sell_btn.disabled = not has_selection
        use_btn.disabled = not has_selection or (self.selected_item and self.selected_item.get("item_type") != "consumable")
        
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
        sell_btn.callback = self._sell_callback
        use_btn.callback = self._use_callback
        
        self.add_item(prev_btn)
        self.add_item(next_btn)
        self.add_item(equip_btn)
        self.add_item(sell_btn)
        self.add_item(use_btn)

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

    async def _refresh_message(self, interaction: discord.Interaction):
        """Refresh the message with current page/selection."""
        self._build_buttons()
        embed = self._build_item_embed(self.selected_item) if self.selected_item else None
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
        if self.selected_item_id:
            self.selected_item = next((i for i in self.items if str(i.get("id")) == self.selected_item_id), None)
            if not self.selected_item:
                self.selected_item_id = None
        self._build_buttons()
        embed = self._build_item_embed(self.selected_item) if self.selected_item else None
        await interaction.edit_original_response(
            content=f"🎒 **{self.char_name}'s Inventory** ({len(self.items)}/{self.max_slots} slots • {self.gold:,}🪙) • Page {self.page + 1}",
            embed=embed,
            view=self,
        )

    def _build_item_embed(self, item: Optional[Dict]) -> Optional[discord.Embed]:
        """Build embed showing item details. Returns None if no item."""
        if not item:
            return None
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
        
        # Stats
        stats = []
        if item.get("s_dmg_min") and item.get("s_dmg_max"):
            stats.append(f"⚔️ **Damage:** {item['s_dmg_min']}-{item['s_dmg_max']}")
        if item.get("s_str"):
            stats.append(f"💪 **Str:** +{item['s_str']}")
        if item.get("s_agi"):
            stats.append(f"⚡ **Agi:** +{item['s_agi']}")
        if item.get("s_int"):
            stats.append(f"🧠 **Int:** +{item['s_int']}")
        if item.get("s_armor"):
            stats.append(f"🛡️ **Armor:** +{item['s_armor']}")
        
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

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("❌ This inventory isn't for you.", ephemeral=True)
            return False
        return True


# ═══════════════════════════════════════════════════════════════════════════
#  DISCORD COG
# ═══════════════════════════════════════════════════════════════════════════

class VisualInventoryCog(commands.Cog, name="Visual Inventory"):
    def __init__(self, bot):
        self.bot = bot
        self.generator = VisualInventoryGenerator()
        self.inv_svc = None
        self.char_svc = None

    async def cog_load(self):
        from services.character.character_service import CharacterService
        from services.character.inventory_service import InventoryService
        self.char_svc = CharacterService(self.bot.db)
        self.inv_svc = InventoryService(self.bot.db)

    @app_commands.command(name="inventory_grid", description="View your inventory as an interactive visual grid")
    @app_commands.describe(category="Filter by category (weapon, armor, consumable, material)")
    async def inventory_grid(
        self,
        interaction: discord.Interaction,
        category: Optional[str] = None,
    ):
        from services.channel_manager import check_channel
        if not await check_channel(interaction, "inventory"):
            return
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)

        char = await self.char_svc.get_character(interaction.user.id)
        if not char:
            return await interaction.followup.send("❌ No character found.")

        items = await self.inv_svc.get_all(char["id"])
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

        # Create box-style inventory view (no image, just buttons)
        view = BoxInventoryView(
            owner_id=interaction.user.id,
            char_id=char["id"],
            char_name=char["name"],
            gold=int(char.get("gold", 0)),
            items=formatted,
            inv_svc=self.inv_svc,
            char_svc=self.char_svc,
            generator=None,  # No image generation
            max_slots=max_slots,
        )

        await interaction.followup.send(
            content=f"🎒 **{char['name']}'s Inventory** ({len(items)}/{max_slots} slots • {int(char.get('gold', 0)):,}🪙)\n\n**💡 Click a slot to select an item and see details!**",
            view=view,
            ephemeral=True,
        )


async def setup(bot):
    await bot.add_cog(VisualInventoryCog(bot))
