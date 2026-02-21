"""
╔══════════════════════════════════════════════════════════════════════════════╗
║    services/profile/profile_card_generator.py — Profile Card Image Gen      ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import logging
import os
from io import BytesIO
from typing import Dict, List, Tuple
from uuid import UUID

from PIL import Image, ImageDraw, ImageFont, ImageFilter

log = logging.getLogger("profile_card")


class ProfileCardGenerator:
    def __init__(self, db):
        self.db = db
        self.cache_dir = "cache/profile_cards"
        os.makedirs(self.cache_dir, exist_ok=True)

    # ── Helper drawing methods ─────────────────────────────────────────────

    @staticmethod
    def _hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
        h = hex_color.lstrip("#")
        return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

    @staticmethod
    def _darken(rgb: Tuple[int, int, int], factor: float = 0.4) -> Tuple[int, int, int]:
        return tuple(max(0, int(c * factor)) for c in rgb)

    @staticmethod
    def _lighten(rgb: Tuple[int, int, int], factor: float = 0.3) -> Tuple[int, int, int]:
        return tuple(min(255, int(c + (255 - c) * factor)) for c in rgb)

    def _load_fonts(self):
        """Try system fonts, fallback gracefully."""
        paths = [
            "/System/Library/Fonts/Helvetica.ttc",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        ]
        fallback_paths = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ]
        font_path = None
        fallback_path = None
        for p in paths:
            if os.path.exists(p):
                font_path = p
                break
        for p in fallback_paths:
            if os.path.exists(p):
                fallback_path = p
                break
        fallback_path = fallback_path or font_path

        if font_path:
            return {
                "title": ImageFont.truetype(font_path, 38),
                "subtitle": ImageFont.truetype(font_path, 24),
                "header": ImageFont.truetype(font_path, 20),
                "body": ImageFont.truetype(fallback_path or font_path, 18),
                "small": ImageFont.truetype(fallback_path or font_path, 15),
                "stat_val": ImageFont.truetype(font_path, 22),
                "stat_lbl": ImageFont.truetype(fallback_path or font_path, 16),
                "bar_text": ImageFont.truetype(font_path, 14),
            }
        else:
            d = ImageFont.load_default()
            return {k: d for k in ("title", "subtitle", "header", "body",
                                    "small", "stat_val", "stat_lbl", "bar_text")}

    # ── Drawing primitives ─────────────────────────────────────────────────

    def _draw_gradient_rect(self, img: Image.Image, box, top_color, bot_color):
        """Vertical linear gradient inside box."""
        x1, y1, x2, y2 = box
        for y in range(y1, y2):
            ratio = (y - y1) / max(1, y2 - y1)
            r = int(top_color[0] + (bot_color[0] - top_color[0]) * ratio)
            g = int(top_color[1] + (bot_color[1] - top_color[1]) * ratio)
            b = int(top_color[2] + (bot_color[2] - top_color[2]) * ratio)
            ImageDraw.Draw(img).line([(x1, y), (x2, y)], fill=(r, g, b))

    def _draw_panel(self, draw: ImageDraw.Draw, box, fill="#1A1D23", border="#2D3139", radius=14):
        """Dark panel with subtle border."""
        draw.rounded_rectangle(box, radius=radius, fill=fill, outline=border, width=2)

    def _draw_bar(self, draw: ImageDraw.Draw, x, y, w, h,
                  value, maximum, color_rgb, radius=8):
        """Modern rounded progress bar with glow effect."""
        pct = max(0.0, min(1.0, value / maximum)) if maximum > 0 else 0
        # Track
        draw.rounded_rectangle([x, y, x + w, y + h], radius=radius,
                               fill="#0D0F12", outline="#2A2E36", width=1)
        # Fill
        fill_w = int((w - 2) * pct)
        if fill_w > 4:
            # Main bar
            draw.rounded_rectangle([x + 1, y + 1, x + 1 + fill_w, y + h - 1],
                                   radius=radius - 1, fill=color_rgb)
            # Highlight stripe (top)
            highlight = self._lighten(color_rgb, 0.35)
            draw.rounded_rectangle([x + 2, y + 2, x + fill_w, y + h // 3],
                                   radius=max(2, radius - 3), fill=highlight)

    def _center_text(self, draw, text, y, font, fill, width):
        bbox = draw.textbbox((0, 0), text, font=font)
        tw = bbox[2] - bbox[0]
        draw.text(((width - tw) // 2, y), text, font=font, fill=fill)

    # ── Main generator ─────────────────────────────────────────────────────

    async def generate_card(self, character_id: UUID, character_data: Dict,
                            stats: Dict, achievements: list) -> BytesIO:
        from config.settings import CLASSES, SPECIALIZATIONS, Settings, RARITIES, ZONES

        W, H = 820, 1080
        MARGIN = 36
        INNER = W - 2 * MARGIN

        card = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        draw = ImageDraw.Draw(card)
        fonts = self._load_fonts()

        # ── Class / spec info ──────────────────────────────────────────────
        class_key = character_data.get("class", "warrior")
        cls = CLASSES.get(class_key)
        spec_key = character_data.get("specialization")
        spec = SPECIALIZATIONS.get(spec_key) if spec_key else None

        accent_map = {
            "fire": "#FF6B35", "frost": "#00CED1", "retribution": "#FF6347",
            "holy_paladin": "#FFD700", "holy_priest": "#F0E68C", "shadow": "#9B59B6",
            "arms": "#E74C3C", "protection": "#3498DB", "assassination": "#C0392B",
            "subtlety": "#1ABC9C", "marksmanship": "#27AE60", "beast_mastery": "#D35400",
        }
        class_accent_map = {
            "warrior": "#C79C6E", "paladin": "#F58CBA", "mage": "#69CCF0",
            "rogue": "#FFF569", "priest": "#E8E8E8", "hunter": "#ABD473",
        }
        accent_hex = accent_map.get(spec_key, class_accent_map.get(class_key, "#69CCF0"))
        accent = self._hex_to_rgb(accent_hex)
        accent_dark = self._darken(accent, 0.25)

        # ── Background ─────────────────────────────────────────────────────
        bg_top = (18, 20, 28)
        bg_bot = (12, 13, 18)
        self._draw_gradient_rect(card, (0, 0, W, H), bg_top, bg_bot)

        # Accent glow at top
        glow = Image.new("RGBA", (W, 200), (0, 0, 0, 0))
        glow_draw = ImageDraw.Draw(glow)
        for i in range(200):
            alpha = int(50 * (1 - i / 200))
            glow_draw.line([(0, i), (W, i)], fill=(*accent_dark, alpha))
        card.paste(Image.alpha_composite(
            Image.new("RGBA", glow.size, (0, 0, 0, 0)), glow), (0, 0))
        draw = ImageDraw.Draw(card)  # refresh after paste

        # Left accent bar
        draw.rectangle([0, 0, 4, H], fill=accent)

        y = 30

        # ── Header ─────────────────────────────────────────────────────────
        char_name = character_data.get("name", "Unknown")
        level = character_data.get("level", 1)

        title_parts = [char_name]
        if spec:
            title_parts.append(spec.name)
        if int(character_data.get("prestige", 0) or 0) > 0:
            title_parts.append(f"Prestige {character_data['prestige']}")

        self._center_text(draw, " · ".join(title_parts), y, fonts["title"], accent, W)
        y += 48
        cls_name = cls.name if cls else class_key.title()
        self._center_text(draw, f"Level {level} {cls_name}", y, fonts["subtitle"], (200, 205, 215), W)
        y += 44

        # thin separator
        draw.rectangle([MARGIN, y, W - MARGIN, y + 1], fill=(45, 49, 57))
        y += 18

        # ── XP Bar ─────────────────────────────────────────────────────────
        if level < Settings.MAX_LEVEL:
            xp_pct = character_data.get("xp_pct", 0)
            xp_cur = character_data.get("xp_current", 0)
            xp_need = character_data.get("xp_needed", 0)
            draw.text((MARGIN, y), f"Experience — {xp_pct}%", fill=(200, 205, 215), font=fonts["header"])
            y += 28
            self._draw_bar(draw, MARGIN, y, INNER, 22, xp_pct, 100, (87, 242, 135))
            y += 26
            draw.text((MARGIN, y), f"{xp_cur:,} / {xp_need:,} XP", fill=(140, 145, 155), font=fonts["small"])
            y += 28
        else:
            self._center_text(draw, "MAX LEVEL ACHIEVED", y, fonts["header"], (255, 215, 0), W)
            y += 38

        # ── HP & Resource Bars ─────────────────────────────────────────────
        draw.rectangle([MARGIN, y, W - MARGIN, y + 1], fill=(45, 49, 57))
        y += 16

        current_hp = character_data.get("current_hp", 0)
        max_hp = character_data.get("max_hp", 1)
        hp_pct = int(current_hp / max_hp * 100) if max_hp else 0

        draw.text((MARGIN, y), "HP", fill=(220, 80, 80), font=fonts["header"])
        hp_pct_text = f"{hp_pct}%"
        bbox = draw.textbbox((0, 0), hp_pct_text, font=fonts["header"])
        draw.text((W - MARGIN - (bbox[2] - bbox[0]), y), hp_pct_text,
                  fill=(220, 80, 80), font=fonts["header"])
        y += 28
        self._draw_bar(draw, MARGIN, y, INNER, 24, current_hp, max_hp, (214, 65, 72))
        y += 28
        draw.text((MARGIN, y), f"{current_hp:,} / {max_hp:,}",
                  fill=(140, 145, 155), font=fonts["small"])
        y += 28

        max_res = character_data.get("max_res", 0)
        if max_res > 0:
            current_res = character_data.get("current_res", 0)
            res_type = character_data.get("res_type", "mana")
            res_name = {"mana": "Mana", "energy": "Energy", "rage": "Rage"}.get(res_type, "Resource")
            res_color = {"mana": (79, 121, 227), "energy": (217, 189, 74), "rage": (215, 84, 84)}.get(res_type, (130, 160, 196))
            res_pct = int(current_res / max_res * 100) if max_res else 0

            draw.text((MARGIN, y), res_name, fill=self._lighten(res_color, 0.3), font=fonts["header"])
            pct_txt = f"{res_pct}%"
            bbox = draw.textbbox((0, 0), pct_txt, font=fonts["header"])
            draw.text((W - MARGIN - (bbox[2] - bbox[0]), y), pct_txt,
                      fill=self._lighten(res_color, 0.3), font=fonts["header"])
            y += 28
            self._draw_bar(draw, MARGIN, y, INNER, 24, current_res, max_res, res_color)
            y += 28
            draw.text((MARGIN, y), f"{current_res:,} / {max_res:,}",
                      fill=(140, 145, 155), font=fonts["small"])
            y += 28

        # ── Stats Panel ────────────────────────────────────────────────────
        draw.rectangle([MARGIN, y, W - MARGIN, y + 1], fill=(45, 49, 57))
        y += 18

        panel_h = 180
        half = (INNER - 20) // 2
        lx = MARGIN
        rx = MARGIN + half + 20

        # Left panel — Core Stats
        self._draw_panel(draw, [lx, y, lx + half, y + panel_h])
        draw.text((lx + 16, y + 12), "Core Stats", fill=accent, font=fonts["header"])
        sy = y + 42
        for label, key in [("STR", "strength"), ("AGI", "agility"),
                           ("INT", "intellect"), ("SPI", "spirit"), ("STA", "stamina")]:
            val = stats.get(key, 0)
            draw.text((lx + 20, sy), label, fill=(150, 155, 165), font=fonts["stat_lbl"])
            draw.text((lx + 70, sy - 2), str(val), fill=(220, 225, 235), font=fonts["stat_val"])
            sy += 26

        # Right panel — Combat Stats
        self._draw_panel(draw, [rx, y, rx + half, y + panel_h])
        draw.text((rx + 16, y + 12), "Combat Stats", fill=accent, font=fonts["header"])
        sy = y + 42
        for label, key, fmt in [("Attack", "attack_power", ""),
                                 ("Spell", "spell_power", ""),
                                 ("Armor", "armor", ""),
                                 ("Crit", "crit_chance", ".1f"),
                                 ("Dodge", "dodge_chance", ".1f")]:
            val = stats.get(key, 0)
            val_str = f"{val:{fmt}}{'%' if fmt else ''}" if fmt else str(val)
            draw.text((rx + 20, sy), label, fill=(150, 155, 165), font=fonts["stat_lbl"])
            draw.text((rx + 100, sy - 2), val_str, fill=(220, 225, 235), font=fonts["stat_val"])
            sy += 26

        y += panel_h + 16

        # ── Info Row: Gold, Location ────────────────────────────────────────
        draw.rectangle([MARGIN, y, W - MARGIN, y + 1], fill=(45, 49, 57))
        y += 14

        gold = character_data.get("gold", 0)
        zone_key = character_data.get("current_zone", "elwynn_forest")
        zone = ZONES.get(zone_key)
        zone_name = zone.name if zone else zone_key.replace("_", " ").title()

        draw.text((MARGIN, y), f"Gold: {gold:,}", fill=(230, 203, 112), font=fonts["body"])
        y += 26
        draw.text((MARGIN, y), f"Location: {zone_name}", fill=(180, 185, 195), font=fonts["body"])
        y += 26

        # Guild
        if character_data.get("guild_name"):
            tag = character_data.get("guild_tag", "")
            gname = character_data.get("guild_name", "")
            glv = character_data.get("guild_level", 1)
            draw.text((MARGIN, y), f"Guild: [{tag}] {gname}  (Lv {glv})",
                      fill=(221, 184, 92), font=fonts["body"])
            y += 26

        y += 8

        # ── Gear + Achievements Row ────────────────────────────────────────
        draw.rectangle([MARGIN, y, W - MARGIN, y + 1], fill=(45, 49, 57))
        y += 14

        equipped = character_data.get("equipped", {})
        gear_slots = ["head", "chest", "main_hand", "legs", "feet"]
        gear_lines = []
        rarity_colors = {
            "common": (157, 157, 157), "uncommon": (30, 255, 0),
            "rare": (0, 112, 221), "epic": (163, 53, 238), "legendary": (255, 128, 0),
        }
        for slot in gear_slots:
            if slot in equipped:
                item = equipped[slot]
                rarity = item.get("rarity", "common")
                color = rarity_colors.get(rarity, (157, 157, 157))
                gear_lines.append((item.get("name", "?"), color))

        # Left column — Equipment
        draw.text((MARGIN, y), "Equipment", fill=accent, font=fonts["header"])
        gy = y + 28
        if gear_lines:
            for name, color in gear_lines[:4]:
                draw.text((MARGIN + 8, gy), name, fill=color, font=fonts["body"])
                gy += 24
        else:
            draw.text((MARGIN + 8, gy), "No items equipped", fill=(120, 125, 135), font=fonts["body"])
            gy += 24

        # Right column — Achievements
        ach_count = len(achievements) if achievements else 0
        draw.text((rx, y), "Achievements", fill=accent, font=fonts["header"])
        draw.text((rx + 8, y + 28), f"{ach_count} earned", fill=(200, 205, 215), font=fonts["body"])

        y = max(gy, y + 56) + 12

        # ── Specialization ─────────────────────────────────────────────────
        if spec:
            draw.rectangle([MARGIN, y, W - MARGIN, y + 1], fill=(45, 49, 57))
            y += 14
            draw.text((MARGIN, y), f"{spec.name} Specialization", fill=accent, font=fonts["header"])
            y += 28
            # Wrap flavor text
            flavor = f'"{spec.flavor}"'
            draw.text((MARGIN + 8, y), flavor[:90], fill=(160, 165, 175), font=fonts["small"])
            y += 22
            if len(flavor) > 90:
                draw.text((MARGIN + 8, y), flavor[90:180], fill=(160, 165, 175), font=fonts["small"])
                y += 22
            passive = f"{spec.passive_name}: {spec.passive_desc}"
            draw.text((MARGIN + 8, y), passive[:95], fill=(200, 205, 215), font=fonts["small"])
            y += 20
            if len(passive) > 95:
                draw.text((MARGIN + 8, y), passive[95:190], fill=(200, 205, 215), font=fonts["small"])
                y += 20
            y += 8

        # ── Footer ─────────────────────────────────────────────────────────
        footer_y = H - 36
        draw.rectangle([MARGIN, footer_y - 8, W - MARGIN, footer_y - 7], fill=(45, 49, 57))
        role = cls.role.title() if cls else "?"
        status = character_data.get("combat_status", "idle").replace("_", " ").title()
        footer = f"World of Discord v{Settings.VERSION}  ·  {role}  ·  {status}"
        self._center_text(draw, footer, footer_y, fonts["small"], (100, 105, 115), W)

        # ── Border ─────────────────────────────────────────────────────────
        draw.rounded_rectangle([2, 2, W - 3, H - 3], radius=18,
                               outline=(*accent_dark, 180), width=2)

        # Convert to RGB for PNG
        final = Image.new("RGB", (W, H), (12, 13, 18))
        final.paste(card, mask=card.split()[3] if card.mode == "RGBA" else None)

        img_bytes = BytesIO()
        final.save(img_bytes, format="PNG", quality=95)
        img_bytes.seek(0)
        return img_bytes
