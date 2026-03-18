"""
Unified Character Panel

Shows Equipment + Inventory in ONE message (image) with toggle buttons.
Uses existing services:
- services.character.character_service.CharacterService
- services.character.inventory_service.InventoryService
"""

from __future__ import annotations

import io
import logging
import os
from typing import Dict, List, Optional
from uuid import UUID

import discord
from PIL import Image, ImageDraw, ImageFont

log = logging.getLogger("cog.character.unified_panel")


class UnifiedCharacterGenerator:
    """Generates Equipment OR Inventory view in a consistent style."""

    COLORS = {
        "bg_dark": "#1E1F22",
        "bg_mid": "#2B2D31",
        "bg_light": "#313338",
        "text_light": "#DCDDDE",
        "text_gray": "#B5BAC1",
        "text_dark": "#80848E",
        "border": "#40444B",
        "legendary": "#FF8C00",
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
        self.font_title, self.font_header, self.font_body, self.font_small, self.font_tiny = self._load_fonts()

    def _load_fonts(self):
        # Prefer bundled/system fonts if present; otherwise PIL default.
        # Note: this bot runs on different OSes; keep it resilient.
        candidates = [
            # Linux (common)
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            # macOS (common)
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
            "/System/Library/Fonts/Supplemental/Arial.ttf",
        ]

        def try_font(path: str, size: int):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                return None

        # Attempt to load bold + regular from the candidate list.
        bold = next((try_font(p, 24) for p in candidates if "Bold" in p and try_font(p, 24)), None)
        reg = next((try_font(p, 18) for p in candidates if "Bold" not in p and try_font(p, 18)), None)
        if not bold or not reg:
            # Fall back to DejaVu if present (even if candidates above failed order)
            try:
                bold = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 24)
                reg = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 18)
            except Exception:
                default = ImageFont.load_default()
                return default, default, default, default, default

        # Size variants
        # Re-open with sizes to avoid weird PIL metrics when resizing font objects.
        try:
            # If we got a path-backed font, it has .path; but PIL may not expose it. Keep simple:
            title = bold.font_variant(size=32) if hasattr(bold, "font_variant") else bold
            header = bold.font_variant(size=24) if hasattr(bold, "font_variant") else bold
            body = reg.font_variant(size=18) if hasattr(reg, "font_variant") else reg
            small = reg.font_variant(size=16) if hasattr(reg, "font_variant") else reg
            tiny = reg.font_variant(size=14) if hasattr(reg, "font_variant") else reg
            return title, header, body, small, tiny
        except Exception:
            default = ImageFont.load_default()
            return default, default, default, default, default

    def generate_view(
        self,
        view_mode: str,
        character_data: Dict,
        equipment_data: Dict,
        inventory_items: List[Dict],
        selected_item: Optional[Dict] = None,
    ) -> io.BytesIO:
        width, height = 1200, 1400
        img = Image.new("RGB", (width, height), color=self.COLORS["bg_mid"])
        draw = ImageDraw.Draw(img)

        draw.rounded_rectangle(
            [20, 20, width - 20, height - 20],
            radius=15,
            fill=self.COLORS["bg_dark"],
            outline=self.COLORS["orange"],
            width=3,
        )

        self._draw_header(draw, character_data)
        self._draw_toggle_buttons(draw, view_mode)

        if view_mode == "equipment":
            self._draw_equipment_view(draw, equipment_data, character_data)
        else:
            self._draw_inventory_view(draw, inventory_items)

        if selected_item:
            self._draw_item_preview(draw, selected_item)

        output = io.BytesIO()
        img.save(output, format="PNG")
        output.seek(0)
        return output

    def _draw_header(self, draw: ImageDraw.ImageDraw, character_data: Dict):
        name = character_data.get("name", "Unknown")
        level = character_data.get("level", 1)
        gold = int(character_data.get("gold", 0) or 0)

        draw.text((40, 35), f"👤 {name}'s Character", fill=self.COLORS["orange"], font=self.font_title)
        draw.text((40, 70), f"Level {level} • {gold:,}🪙", fill=self.COLORS["text_gray"], font=self.font_small)

    def _draw_toggle_buttons(self, draw: ImageDraw.ImageDraw, view_mode: str):
        toggle_y = 120

        equipment_active = view_mode == "equipment"
        equipment_bg = self.COLORS["orange"] if equipment_active else self.COLORS["bg_mid"]
        equipment_text = self.COLORS["bg_dark"] if equipment_active else self.COLORS["text_gray"]
        draw.rounded_rectangle(
            [40, toggle_y, 240, toggle_y + 50],
            radius=10,
            fill=equipment_bg,
            outline=self.COLORS["text_gray"] if not equipment_active else None,
            width=2 if not equipment_active else 0,
        )
        draw.text((75, toggle_y + 13), "🛡️ Equipment", fill=equipment_text, font=self.font_header)

        inventory_active = view_mode == "inventory"
        inventory_bg = self.COLORS["orange"] if inventory_active else self.COLORS["bg_mid"]
        inventory_text = self.COLORS["bg_dark"] if inventory_active else self.COLORS["text_gray"]
        draw.rounded_rectangle(
            [250, toggle_y, 450, toggle_y + 50],
            radius=10,
            fill=inventory_bg,
            outline=self.COLORS["text_gray"] if not inventory_active else None,
            width=2 if not inventory_active else 0,
        )
        draw.text((285, toggle_y + 13), "🎒 Inventory", fill=inventory_text, font=self.font_header)

        draw.text((470, toggle_y + 15), "← Click to switch views", fill=self.COLORS["text_gray"], font=self.font_small)

    def _draw_equipment_view(self, draw: ImageDraw.ImageDraw, equipment_data: Dict, character_data: Dict):
        content_y = 200
        char_x, char_y = 500, 550

        char_size = 200
        draw.ellipse(
            [char_x - char_size // 2, char_y - char_size // 2, char_x + char_size // 2, char_y + char_size // 2],
            fill="#1A1C1E",
        )

        char_emoji = self._get_character_emoji(character_data.get("class", "warrior"))
        draw.text((char_x - 50, char_y - 70), char_emoji, fill=self.COLORS["text_light"], font=self.font_title)

        self._draw_equipment_slots(draw, char_x, char_y, equipment_data)
        self._draw_stats_panel(draw, 900, content_y, character_data)

    def _draw_equipment_slots(self, draw: ImageDraw.ImageDraw, char_x: int, char_y: int, equipment_data: Dict):
        slot_positions = [
            ("head", "🪖", 0, -200),
            ("neck", "📿", -180, -100),
            ("shoulders", "🧤", -180, -20),
            ("chest", "🥋", -180, 60),
            ("hands", "🧤", -180, 140),
            ("main_hand", "⚔️", 180, -100),
            ("off_hand", "🛡️", 180, -20),
            ("waist", "🔗", 180, 60),
            ("legs", "👖", 180, 140),
            ("feet", "👢", -70, 200),
            ("ring", "💍", 70, 200),
            ("trinket", "🔮", 0, 240),
        ]

        slot_size = 70
        for slot_name, emoji, x_off, y_off in slot_positions:
            x = char_x + x_off
            y = char_y + y_off
            item = equipment_data.get(slot_name)

            if item:
                rarity_color = self.COLORS.get(item.get("rarity", "common"), self.COLORS["common"])
                draw.rounded_rectangle(
                    [x - slot_size // 2, y - slot_size // 2, x + slot_size // 2, y + slot_size // 2],
                    radius=10,
                    fill=self.COLORS["bg_light"],
                    outline=rarity_color,
                    width=3,
                )
                item_emoji = item.get("icon", emoji)
                draw.text((x - 15, y - 20), item_emoji, fill=rarity_color, font=self.font_header)
                name = (item.get("name", "") or "")[:8]
                draw.text((x - 35, y + 10), name, fill=rarity_color, font=self.font_tiny)
            else:
                draw.rounded_rectangle(
                    [x - slot_size // 2, y - slot_size // 2, x + slot_size // 2, y + slot_size // 2],
                    radius=10,
                    fill=self.COLORS["bg_dark"],
                    outline=self.COLORS["border"],
                    width=2,
                )
                draw.text((x - 15, y - 20), emoji, fill=self.COLORS["border"], font=self.font_header)
                draw.text((x - 20, y + 10), "Empty", fill=self.COLORS["border"], font=self.font_tiny)

            label = slot_name.replace("_", " ").title()
            draw.text((x - 30, y - slot_size // 2 - 18), label, fill=self.COLORS["text_gray"], font=self.font_tiny)

    def _draw_stats_panel(self, draw: ImageDraw.ImageDraw, x: int, y: int, character_data: Dict):
        width, height = 260, 500
        draw.rounded_rectangle([x, y, x + width, y + height], radius=12, fill=self.COLORS["bg_mid"])
        draw.text((x + 15, y + 15), "📊 Total Stats", fill=self.COLORS["text_light"], font=self.font_header)

        stat_y = y + 55
        stats = character_data.get("stats", {}) or {}
        stat_list = [
            ("💪 Strength", stats.get("strength", 0)),
            ("⚡ Agility", stats.get("agility", 0)),
            ("🧠 Intellect", stats.get("intellect", 0)),
            ("❤️ Stamina", stats.get("stamina", 0)),
            ("", ""),
            ("⚔️ Attack", stats.get("attack", 0)),
            ("🛡️ Armor", stats.get("armor", 0)),
        ]
        for stat_name, stat_value in stat_list:
            if stat_name:
                draw.text((x + 20, stat_y), stat_name, fill=self.COLORS["text_gray"], font=self.font_small)
                draw.text((x + 180, stat_y), str(stat_value), fill=self.COLORS["green"], font=self.font_small)
            stat_y += 28

    def _draw_inventory_view(self, draw: ImageDraw.ImageDraw, inventory_items: List[Dict]):
        content_y = 200
        grid_x, grid_y = 40, content_y
        cell_size, gap, cols, rows = 80, 10, 14, 8

        for idx in range(cols * rows):
            row, col = idx // cols, idx % cols
            x = grid_x + col * (cell_size + gap)
            y = grid_y + row * (cell_size + gap)
            if idx < len(inventory_items):
                self._draw_inventory_cell(draw, inventory_items[idx], x, y, cell_size)
            else:
                self._draw_empty_cell(draw, x, y, cell_size)

    def _draw_inventory_cell(self, draw: ImageDraw.ImageDraw, item: Dict, x: int, y: int, size: int):
        rarity_color = self.COLORS.get(item.get("rarity", "common"), self.COLORS["common"])
        draw.rounded_rectangle(
            [x, y, x + size, y + size],
            radius=8,
            fill=self.COLORS["bg_light"],
            outline=rarity_color,
            width=3,
        )
        icon = item.get("icon", "📦")
        draw.text((x + size // 2 - 15, y + 15), icon, fill=rarity_color, font=self.font_header)

        enhancement = int(item.get("enhancement_level", 0) or 0)
        if enhancement > 0:
            draw.rounded_rectangle([x + size - 28, y + 5, x + size - 5, y + 22], radius=4, fill=self.COLORS["bg_dark"])
            draw.text((x + size - 24, y + 6), f"+{enhancement}", fill=self.COLORS["orange"], font=self.font_tiny)

        quantity = int(item.get("quantity", 1) or 1)
        if quantity > 1:
            draw.rounded_rectangle(
                [x + size - 38, y + size - 22, x + size - 5, y + size - 5], radius=4, fill=self.COLORS["bg_dark"]
            )
            draw.text((x + size - 34, y + size - 20), f"x{quantity}", fill=self.COLORS["text_light"], font=self.font_tiny)

        name = (item.get("name", "") or "")[:7]
        draw.text((x + 5, y + size - 18), name, fill=self.COLORS["text_gray"], font=self.font_tiny)

    def _draw_empty_cell(self, draw: ImageDraw.ImageDraw, x: int, y: int, size: int):
        draw.rounded_rectangle(
            [x, y, x + size, y + size], radius=8, fill=self.COLORS["bg_dark"], outline=self.COLORS["border"], width=2
        )
        draw.text((x + size // 2 - 10, y + size // 2 - 10), "＋", fill=self.COLORS["border"], font=self.font_header)

    def _draw_item_preview(self, draw: ImageDraw.ImageDraw, item: Dict):
        preview_y = 1120
        width = 1160
        rarity_color = self.COLORS.get(item.get("rarity", "common"), self.COLORS["common"])

        draw.rounded_rectangle(
            [40, preview_y, 40 + width, preview_y + 240], radius=12, fill=self.COLORS["bg_dark"], outline=rarity_color, width=2
        )

        name = item.get("name", "Unknown")
        enhancement = int(item.get("enhancement_level", 0) or 0)
        if enhancement > 0:
            name = f"{name} +{enhancement}"
        draw.text((50, preview_y + 15), f"🔍 Selected: {name}", fill=rarity_color, font=self.font_header)

        detail_y = preview_y + 60
        draw.text((60, detail_y), "📊 Stats", fill=self.COLORS["text_gray"], font=self.font_body)
        detail_y += 30

        for stat_name, stat_key in [("⚔️ Damage", "damage"), ("💪 STR", "s_str"), ("⚡ AGI", "s_agi")]:
            stat_value = item.get(stat_key, 0) or 0
            if stat_value:
                draw.text((70, detail_y), stat_name, fill=self.COLORS["text_gray"], font=self.font_small)
                draw.text((200, detail_y), str(stat_value), fill=self.COLORS["green"], font=self.font_small)
                detail_y += 22

    def _get_character_emoji(self, class_name: str) -> str:
        emojis = {
            "warrior": "⚔️",
            "mage": "🧙‍♂️",
            "priest": "🙏",
            "rogue": "🥷",
            "hunter": "🏹",
            "warlock": "🔮",
            "paladin": "🛡️",
        }
        return emojis.get((class_name or "").lower(), "🧙‍♂️")


class _InventorySelect(discord.ui.Select):
    def __init__(self, owner_id: int, items: List[Dict]):
        self.owner_id = owner_id
        self._items_by_id: Dict[str, Dict] = {str(i["id"]): i for i in items if i.get("id")}

        options: List[discord.SelectOption] = []
        for i in items[:25]:
            name = i.get("name", "Item")
            rarity = (i.get("rarity") or "common").title()
            qty = int(i.get("quantity", 1) or 1)
            enh = int(i.get("enhancement_level", 0) or 0)
            enh_txt = f" +{enh}" if enh > 0 else ""
            label = f"{name}{enh_txt}"
            desc = f"{rarity}" + (f" • x{qty}" if qty > 1 else "")
            options.append(
                discord.SelectOption(
                    label=label[:100],
                    description=desc[:100],
                    value=str(i["id"]),
                    emoji=i.get("icon", "📦"),
                )
            )

        super().__init__(placeholder="Select an item…", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        view = self.view
        if not isinstance(view, UnifiedCharacterView):
            return await interaction.response.send_message("❌ Internal error.", ephemeral=True)
        if interaction.user.id != self.owner_id:
            return await interaction.response.send_message("❌ This menu isn’t for you.", ephemeral=True)

        item = self._items_by_id.get(self.values[0])
        view.selected_item = item
        await view.update_view(interaction)


class UnifiedCharacterView(discord.ui.View):
    def __init__(
        self,
        *,
        owner_id: int,
        character_id: UUID,
        generator: UnifiedCharacterGenerator,
        char_service,
        inv_service,
    ):
        super().__init__(timeout=600)
        self.owner_id = owner_id
        self.character_id = character_id
        self.generator = generator
        self.char_service = char_service
        self.inv_service = inv_service

        self.view_mode = "equipment"
        self.selected_item: Optional[Dict] = None
        self._select: Optional[_InventorySelect] = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("❌ This panel isn’t for you.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="🛡️ Equipment", style=discord.ButtonStyle.primary, row=0, custom_id="ucp_equipment")
    async def show_equipment(self, interaction: discord.Interaction, _button: discord.ui.Button):
        if self.view_mode != "equipment":
            self.view_mode = "equipment"
            await self.update_view(interaction)
        else:
            await interaction.response.send_message("Already viewing equipment.", ephemeral=True)

    @discord.ui.button(label="🎒 Inventory", style=discord.ButtonStyle.secondary, row=0, custom_id="ucp_inventory")
    async def show_inventory(self, interaction: discord.Interaction, _button: discord.ui.Button):
        if self.view_mode != "inventory":
            self.view_mode = "inventory"
            await self.update_view(interaction)
        else:
            await interaction.response.send_message("Already viewing inventory.", ephemeral=True)

    @discord.ui.button(label="⚡ Equip", style=discord.ButtonStyle.success, row=2, custom_id="ucp_equip")
    async def equip_item(self, interaction: discord.Interaction, _button: discord.ui.Button):
        if not self.selected_item:
            return await interaction.response.send_message("Select an item first.", ephemeral=True)
        if self.selected_item.get("is_equipped"):
            return await interaction.response.send_message("That item is already equipped.", ephemeral=True)
        if not self.selected_item.get("equip_slot"):
            return await interaction.response.send_message("That item can’t be equipped.", ephemeral=True)

        try:
            uid = UUID(str(self.selected_item["id"]))
        except Exception:
            return await interaction.response.send_message("Invalid item ID.", ephemeral=True)

        await interaction.response.defer(ephemeral=True)
        ok, msg = await self.inv_service.equip(self.character_id, uid)
        await interaction.followup.send(f"{'✅' if ok else '❌'} {msg}", ephemeral=True)
        await self.update_view(interaction)

    @discord.ui.button(label="💰 Sell", style=discord.ButtonStyle.secondary, row=2, custom_id="ucp_sell")
    async def sell_item(self, interaction: discord.Interaction, _button: discord.ui.Button):
        if not self.selected_item:
            return await interaction.response.send_message("Select an item first.", ephemeral=True)
        if self.selected_item.get("is_equipped"):
            return await interaction.response.send_message("Unequip it first.", ephemeral=True)

        try:
            uid = UUID(str(self.selected_item["id"]))
        except Exception:
            return await interaction.response.send_message("Invalid item ID.", ephemeral=True)

        await interaction.response.defer(ephemeral=True)
        ok, msg, gold = await self.inv_service.sell(self.character_id, uid)
        if ok and gold:
            await self.char_service.add_gold(self.character_id, gold, "vendor sale")
        await interaction.followup.send(f"{'✅' if ok else '❌'} {msg}", ephemeral=True)
        if ok:
            self.selected_item = None
        await self.update_view(interaction)

    async def update_view(self, interaction: discord.Interaction):
        # Fetch latest data
        char = await self.char_service.get_by_id(self.character_id)
        if not char:
            return await interaction.response.send_message("❌ Character not found.", ephemeral=True)

        stats = await self.char_service.total_stats(self.character_id)
        equipped = await self.inv_service.get_equipped(self.character_id)
        all_items = await self.inv_service.get_all(self.character_id)

        # Inventory panel generally means "bag": hide equipped items there (matches your /inventory behavior)
        bag_items = [i for i in all_items if not i.get("is_equipped")]

        character_data = {
            "name": char.get("name", "Unknown"),
            "level": int(char.get("level", 1) or 1),
            "gold": int(char.get("gold", 0) or 0),
            "class": char.get("class", "warrior"),
            "stats": {
                "strength": int(stats.get("strength", 0) or 0),
                "agility": int(stats.get("agility", 0) or 0),
                "intellect": int(stats.get("intellect", 0) or 0),
                "stamina": int(stats.get("stamina", 0) or 0),
                "attack": int(stats.get("attack_power", 0) or 0),
                "armor": int(stats.get("armor", 0) or 0),
            },
        }

        equipment_data: Dict[str, Dict] = {}
        for slot, item in (equipped or {}).items():
            equipment_data[str(slot)] = {
                "id": str(item.get("id")),
                "name": item.get("name", "?"),
                "rarity": item.get("rarity", "common"),
                "icon": item.get("icon", "📦"),
            }

        inventory_items: List[Dict] = []
        for item in bag_items[:112]:
            inv = {
                "id": str(item.get("id")),
                "name": item.get("name", "?"),
                "rarity": item.get("rarity", "common"),
                "icon": item.get("icon", "📦"),
                "template_id": item.get("template_id"),
                "quantity": int(item.get("quantity", 1) or 1),
                "enhancement_level": int(item.get("enhancement_level", 0) or 0),
                "equip_slot": item.get("equip_slot"),
                "is_equipped": bool(item.get("is_equipped", False)),
                # Extra fields for preview stats
                "s_str": int(item.get("s_str", 0) or 0),
                "s_agi": int(item.get("s_agi", 0) or 0),
            }
            dmg_min = int(item.get("s_dmg_min", 0) or 0)
            dmg_max = int(item.get("s_dmg_max", 0) or 0)
            inv["damage"] = (dmg_min + dmg_max) // 2 if (dmg_min or dmg_max) else 0
            inventory_items.append(inv)

        # Rebuild inventory select when in inventory mode
        if self.view_mode == "inventory":
            if self._select:
                try:
                    self.remove_item(self._select)
                except Exception:
                    pass
            self._select = _InventorySelect(owner_id=self.owner_id, items=inventory_items)
            self.add_item(self._select)
        else:
            if self._select:
                try:
                    self.remove_item(self._select)
                except Exception:
                    pass
                self._select = None

        # Update toggle styles (children[0] and children[1] are the toggle buttons)
        try:
            self.children[0].style = discord.ButtonStyle.primary if self.view_mode == "equipment" else discord.ButtonStyle.secondary
            self.children[1].style = discord.ButtonStyle.primary if self.view_mode == "inventory" else discord.ButtonStyle.secondary
        except Exception:
            pass

        # Prefer Vercel renderer if configured; fall back to local Pillow generator.
        image_bytes = None
        render_base = (os.getenv("RENDER_API_BASE_URL") or "").strip()
        if render_base:
            try:
                from services.render_api import post_png, icon_url_for_template, icon_url_for_item_name

                base = render_base.rstrip("/")

                if self.view_mode == "inventory":
                    max_slots = int(os.getenv("RENDER_INVENTORY_MAX_SLOTS", "40") or 40)
                    items_payload = []
                    for idx, it in enumerate(inventory_items[:max_slots]):
                        # Icons are named by display name (e.g. "Iron Sword.png"); fallback to template_id
                        item_name = it.get("name") or ""
                        icon_url = (icon_url_for_item_name(item_name) or icon_url_for_template(it.get("template_id") or "") or "")
                        items_payload.append(
                            {
                                "id": it.get("id", str(idx)),
                                "name": it.get("name", "Item"),
                                "icon": icon_url,
                                "rarity": it.get("rarity", "common"),
                                "quantity": int(it.get("quantity", 1) or 1),
                                "slotIndex": idx,
                            }
                        )
                    payload = {
                        "items": items_payload,
                        "maxSlots": max_slots,
                        "gold": int(character_data.get("gold", 0) or 0),
                        "playerName": character_data.get("name", "Adventurer"),
                    }
                    image_bytes = await post_png("/api/render-inventory", payload)
                else:
                    # Map bot equip slots -> renderer slot ids (see lib/game-types.ts in renderer)
                    slot_map = {
                        "head": "head",
                        "neck": "neck",
                        "shoulders": "shoulder",
                        "chest": "chest",
                        "hands": "gloves",
                        "waist": "belt",
                        "legs": "legs",
                        "feet": "boots",
                        "main_hand": "mainhand",
                        "off_hand": "offhand",
                        "ring": "ring1",
                    }

                    equipped_payload: Dict[str, Dict] = {}
                    for bot_slot, item in (equipped or {}).items():
                        renderer_slot = slot_map.get(str(bot_slot))
                        if not renderer_slot:
                            continue
                        # Icons are named by display name (e.g. "Iron Sword.png")
                        item_name = item.get("name") or ""
                        icon_url = (icon_url_for_item_name(item_name) or icon_url_for_template(item.get("template_id") or "") or "")
                        equipped_payload[renderer_slot] = {
                            "slot": renderer_slot,
                            "name": item.get("name", "?"),
                            "icon": icon_url,
                            "rarity": item.get("rarity", "common"),
                        }

                    payload = {
                        "equipped": equipped_payload,
                        "stats": {
                            "attack": int(stats.get("attack_power", 0) or 0),
                            "defense": int(stats.get("armor", 0) or 0),
                            "hp": int(char.get("max_hp", 0) or 0),
                            "speed": int(stats.get("haste", 0) or 0),
                            "level": int(char.get("level", 1) or 1),
                            "class": (char.get("class") or "Adventurer").title(),
                            "name": char.get("name", "Adventurer"),
                        },
                    }
                    image_bytes = await post_png("/api/render-equipment", payload)
            except Exception:
                image_bytes = None

        if image_bytes is None:
            image_bytes = self.generator.generate_view(
                view_mode=self.view_mode,
                character_data=character_data,
                equipment_data=equipment_data,
                inventory_items=inventory_items,
                selected_item=self.selected_item,
            )

        # Ensure we edit the same message (ephemeral or not)
        if interaction.response.is_done():
            await interaction.edit_original_response(attachments=[discord.File(fp=image_bytes, filename="character.png")], view=self)
        else:
            await interaction.response.edit_message(attachments=[discord.File(fp=image_bytes, filename="character.png")], view=self)

