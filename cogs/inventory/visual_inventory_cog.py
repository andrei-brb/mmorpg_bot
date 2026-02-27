"""
╔══════════════════════════════════════════════════════════════════════════════╗
║         VISUAL INVENTORY - Beautiful Grid Layout for mmorpg_bot             ║
╚══════════════════════════════════════════════════════════════════════════════╝

Generates inventory images with rarity borders, enhancement levels, and grid layout.
Command: /inventory_grid [category]
"""

import io
import logging
from typing import List, Dict, Optional

import discord
from discord import app_commands
from discord.ext import commands
from PIL import Image, ImageDraw, ImageFont

from config.settings import Settings

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
        category_filter: Optional[str] = None,
        selected_item: Optional[Dict] = None,
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
                self._draw_item_cell(draw, item, x, y, cell_size, selected_item and str(item.get("id")) == str(selected_item.get("id")))
            else:
                self._draw_empty_cell(draw, x, y, cell_size)

        # Sidebar (selected item)
        if selected_item:
            self._draw_sidebar(draw, selected_item)

        output = io.BytesIO()
        img.save(output, format="PNG")
        output.seek(0)
        return output

    def _draw_item_cell(self, draw, item: Dict, x: int, y: int, size: int, is_selected: bool = False):
        draw.rounded_rectangle([x, y, x + size, y + size], radius=8, fill=self.COLORS["bg_light"])
        rarity = item.get("rarity", "common")
        rarity_color = self.COLORS.get(rarity, self.COLORS["common"])
        draw.rounded_rectangle([x - 1, y - 1, x + size + 1, y + size + 1], radius=8, outline=rarity_color, width=4 if is_selected else 3)
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

    def _draw_sidebar(self, draw, item: Dict):
        sx, sy, sw = 700, 140, 270
        draw.rounded_rectangle([sx, sy, sx + sw, sy + 550], radius=12, fill=self.COLORS["bg_dark"])
        draw.text((sx + 10, sy + 20), "📦 Selected Item", fill=self.COLORS["text_gray"], font=self.font_small)
        rarity_color = self.COLORS.get(item.get("rarity", "common"), self.COLORS["common"])
        draw.rounded_rectangle([sx + 10, sy + 55, sx + sw - 10, sy + 280], radius=8, fill=self.COLORS["bg_mid"], outline=rarity_color, width=3)
        icon = item.get("icon", "📦")
        draw.text((sx + 105, sy + 75), icon, fill=rarity_color, font=self.font_icon_large)
        name = item.get("name", "?")
        enh = item.get("enhancement_level", 0) or 0
        if enh > 0:
            name = f"{name} +{enh}"
        draw.text((sx + 25, sy + 155), name[:22], fill=rarity_color, font=self.font_header)
        stats_y = sy + 195
        for label, val in [
            ("⚔️ Damage:", f"{item.get('s_dmg_min', 0)}-{item.get('s_dmg_max', 0)}" if item.get("s_dmg_min") else "N/A"),
            ("💪 Str:", f"+{item.get('s_str', 0) or 0}"),
            ("⚡ Agi:", f"+{item.get('s_agi', 0) or 0}"),
            ("🧠 Int:", f"+{item.get('s_int', 0) or 0}"),
        ]:
            if val != "N/A" and val != "+0":
                draw.text((sx + 20, stats_y), label, fill=self.COLORS["text_gray"], font=self.font_small)
                draw.text((sx + 170, stats_y), str(val), fill=self.COLORS["green"], font=self.font_small)
                stats_y += 22
        desc = item.get("description", "A mysterious item.")[:120]
        draw.text((sx + 10, sy + 300), f"📜 {desc}...", fill=self.COLORS["text_dark"], font=self.font_tiny)


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

    @app_commands.command(name="inventory_grid", description="View your inventory as a visual grid")
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
                "s_dmg_min": item.get("s_dmg_min"),
                "s_dmg_max": item.get("s_dmg_max"),
                "s_str": item.get("s_str"),
                "s_agi": item.get("s_agi"),
                "s_int": item.get("s_int"),
                "description": item.get("description", ""),
            })

        selected = formatted[0] if formatted else None
        player = await self.bot.db.fetchrow(
            "SELECT p.is_premium FROM players p JOIN characters c ON c.player_id=p.id WHERE c.id=$1",
            char["id"],
        )
        max_slots = Settings.PREMIUM_INVENTORY_SLOTS if (player and player["is_premium"]) else Settings.FREE_INVENTORY_SLOTS

        image_bytes = self.generator.generate_inventory_image(
            items=formatted,
            character_name=char["name"],
            gold=int(char.get("gold", 0)),
            max_slots=max_slots,
            category_filter=category,
            selected_item=selected,
        )

        file = discord.File(fp=image_bytes, filename="inventory.png")
        await interaction.followup.send(
            content=f"🎒 **{char['name']}'s Inventory** ({len(items)} items)",
            file=file,
            ephemeral=True,
        )


async def setup(bot):
    await bot.add_cog(VisualInventoryCog(bot))
