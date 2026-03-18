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

import aiohttp
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

    async def _fetch_image(self, url: str, *, timeout_s: float = 10.0) -> Image.Image | None:
        if not url:
            return None
        try:
            timeout = aiohttp.ClientTimeout(total=timeout_s)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url) as resp:
                    if resp.status != 200:
                        return None
                    data = await resp.read()
            im = Image.open(BytesIO(data)).convert("RGBA")
            return im
        except Exception:
            return None

    @staticmethod
    def _circle_crop(im: Image.Image, size: int) -> Image.Image:
        im = im.convert("RGBA").resize((size, size), Image.Resampling.LANCZOS)
        mask = Image.new("L", (size, size), 0)
        d = ImageDraw.Draw(mask)
        d.ellipse([0, 0, size - 1, size - 1], fill=255)
        out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        out.paste(im, (0, 0), mask)
        return out

    @staticmethod
    def _vignette(size: tuple[int, int], strength: float = 0.75) -> Image.Image:
        w, h = size
        v = Image.new("L", (w, h), 0)
        d = ImageDraw.Draw(v)
        # big soft ellipse centered; corners darker
        d.ellipse([-w * 0.15, -h * 0.10, w * 1.15, h * 1.10], fill=255)
        v = v.filter(ImageFilter.GaussianBlur(radius=min(w, h) * 0.08))
        # invert and scale
        inv = Image.eval(v, lambda p: int((255 - p) * strength))
        return inv

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

        # Match the reference card proportions closely
        W, H = 700, 1050
        MARGIN = 40
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

        # ── Background (dark + texture + vignette) ─────────────────────────
        bg_top = (20, 18, 16)
        bg_bot = (10, 10, 12)
        self._draw_gradient_rect(card, (0, 0, W, H), bg_top, bg_bot)

        # subtle noise texture
        noise = Image.effect_noise((W, H), 12).convert("L")
        noise = ImageEnhance.Contrast(noise).enhance(0.8)
        noise_rgba = Image.merge("RGBA", (noise, noise, noise, Image.new("L", (W, H), 25)))
        card = Image.alpha_composite(card, noise_rgba)

        # vignette
        vig = self._vignette((W, H), 0.9)
        vig_rgba = Image.merge("RGBA", (Image.new("L", (W, H), 0),) * 3 + (vig,))
        card = Image.alpha_composite(card, vig_rgba)
        draw = ImageDraw.Draw(card)

        # warm gold sparkles
        import random
        r = random.Random(int(character_id.int % (2**32)))
        spark = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        sd = ImageDraw.Draw(spark)
        for _ in range(120):
            x = r.randint(0, W - 1)
            y = r.randint(0, H - 1)
            a = r.randint(10, 55)
            col = (255, 210, 120, a)
            sd.ellipse([x, y, x + 2, y + 2], fill=col)
        spark = spark.filter(ImageFilter.GaussianBlur(radius=1.2))
        card = Image.alpha_composite(card, spark)
        draw = ImageDraw.Draw(card)

        # ── Ornate gold frame ───────────────────────────────────────────────
        outer = [16, 16, W - 16, H - 16]
        inner = [26, 26, W - 26, H - 26]
        gold = (222, 186, 110)
        gold2 = (160, 120, 60)
        draw.rounded_rectangle(outer, radius=24, outline=gold, width=4)
        draw.rounded_rectangle(inner, radius=22, outline=gold2, width=2)

        # corner accents
        for (cx, cy, sx, sy) in [(26, 26, 1, 1), (W - 26, 26, -1, 1), (26, H - 26, 1, -1), (W - 26, H - 26, -1, -1)]:
            draw.line([cx, cy, cx + 40 * sx, cy], fill=gold, width=3)
            draw.line([cx, cy, cx, cy + 40 * sy], fill=gold, width=3)
            draw.ellipse([cx - 10, cy - 10, cx + 10, cy + 10], outline=gold, width=2)

        y = 54

        # ── Avatar circle (top-left) ───────────────────────────────────────
        avatar_url = character_data.get("avatar_url") or ""
        avatar = await self._fetch_image(str(avatar_url)) if avatar_url else None
        av_size = 110
        av_x, av_y = 70, 92
        # gold ring + glow
        ring = Image.new("RGBA", (av_size + 18, av_size + 18), (0, 0, 0, 0))
        rd = ImageDraw.Draw(ring)
        rd.ellipse([0, 0, ring.size[0] - 1, ring.size[1] - 1], outline=(255, 220, 140, 255), width=6)
        rd.ellipse([6, 6, ring.size[0] - 7, ring.size[1] - 7], outline=(150, 110, 60, 255), width=2)
        ring = ring.filter(ImageFilter.GaussianBlur(radius=0.6))
        card.paste(ring, (av_x - ring.size[0] // 2, av_y - ring.size[1] // 2), ring)

        if avatar is None:
            # placeholder
            ph = Image.new("RGBA", (av_size, av_size), (30, 30, 34, 255))
            pd = ImageDraw.Draw(ph)
            pd.ellipse([0, 0, av_size - 1, av_size - 1], fill=(28, 28, 30, 255))
            avatar_c = self._circle_crop(ph, av_size)
        else:
            avatar_c = self._circle_crop(avatar, av_size)
        card.paste(avatar_c, (av_x - av_size // 2, av_y - av_size // 2), avatar_c)
        draw = ImageDraw.Draw(card)

        # ── Header text (right of avatar) ──────────────────────────────────
        char_name = character_data.get("name", "Unknown")
        level = character_data.get("level", 1)
        cls_name = cls.name if cls else class_key.title()
        spec_line = f"★ {spec.name} Specialist" if spec else ""

        name_x = 150
        draw.text((name_x, 60), str(char_name), fill=(240, 210, 150), font=fonts["title"])
        draw.text((name_x, 104), f"Level {level} {cls_name}", fill=(180, 210, 160), font=fonts["subtitle"])
        if spec_line:
            draw.text((name_x, 136), spec_line, fill=(200, 190, 150), font=fonts["body"])

        # thin separator
        y = 180
        draw.line([MARGIN, y, W - MARGIN, y], fill=(120, 95, 55), width=1)
        y += 18

        # ── HP & Resource bars (styled like reference) ─────────────────────
        def draw_ref_bar(label, value, maximum, y0, color):
            bar_h = 30
            bar_x = MARGIN + 40
            bar_w = INNER - 40
            # frame
            draw.rounded_rectangle([MARGIN, y0, W - MARGIN, y0 + bar_h + 10], radius=14, outline=(160, 120, 60), width=2, fill=(20, 18, 16, 160))
            draw.text((MARGIN + 20, y0 + 10), label, fill=(235, 220, 200), font=fonts["header"])
            # track
            tx, ty = bar_x, y0 + 10
            draw.rounded_rectangle([tx, ty, tx + bar_w, ty + bar_h - 10], radius=10, fill=(40, 28, 20), outline=(120, 90, 55), width=1)
            pct = 0 if maximum <= 0 else max(0, min(1, value / maximum))
            fw = int((bar_w - 2) * pct)
            if fw > 0:
                draw.rounded_rectangle([tx + 1, ty + 1, tx + 1 + fw, ty + bar_h - 11], radius=9, fill=color)
            txt = f"{int(value):,} / {int(maximum):,}"
            bbox = draw.textbbox((0, 0), txt, font=fonts["bar_text"])
            draw.text((tx + bar_w/2 - (bbox[2]-bbox[0])/2, ty + 2), txt, fill=(255, 240, 220), font=fonts["bar_text"])

        current_hp = int(character_data.get("current_hp", 0) or 0)
        max_hp = int(character_data.get("max_hp", 1) or 1)
        draw_ref_bar("HP", current_hp, max_hp, y, (200, 55, 55))
        y += 70

        max_res = int(character_data.get("max_res", 0) or 0)
        current_res = int(character_data.get("current_res", 0) or 0)
        res_type = character_data.get("res_type", "mana")
        res_name = {"mana": "Mana", "energy": "Energy", "rage": "Rage"}.get(res_type, "Resource")
        res_color = {"mana": (70, 120, 220), "energy": (240, 180, 40), "rage": (200, 55, 55)}.get(res_type, (200, 160, 80))
        if max_res > 0:
            draw_ref_bar(res_name, current_res, max_res, y, res_color)
            y += 78
        else:
            y += 10

        # ── Stats panels like reference ─────────────────────────────────────
        y += 6
        panel_h = 220
        half = (INNER - 18) // 2
        lx = MARGIN
        rx = MARGIN + half + 18

        self._draw_panel(draw, [lx, y, lx + half, y + panel_h], fill="#141316", border="#3c2b17", radius=14)
        self._draw_panel(draw, [rx, y, rx + half, y + panel_h], fill="#141316", border="#3c2b17", radius=14)
        draw.text((lx + 16, y + 12), "Core Stats", fill=(235, 205, 150), font=fonts["header"])
        draw.text((rx + 16, y + 12), "Combat Stats", fill=(235, 205, 150), font=fonts["header"])

        sy = y + 54
        core = [("STR", stats.get("strength", 0), (220, 190, 120)),
                ("AGI", stats.get("agility", 0), (120, 220, 120)),
                ("INT", stats.get("intellect", 0), (120, 180, 240)),
                ("SPI", stats.get("spirit", 0), (180, 120, 240)),
                ("STA", stats.get("stamina", 0), (220, 120, 120))]
        for lbl, val, col in core:
            draw.text((lx + 22, sy), lbl, fill=(220, 210, 200), font=fonts["stat_lbl"])
            draw.text((lx + half - 30, sy - 2), str(val), fill=col, font=fonts["stat_val"], anchor="ra")
            sy += 32

        sy = y + 54
        combat = [("Attack", stats.get("attack_power", 0), (235, 205, 150)),
                  ("Spell", stats.get("spell_power", 0), (235, 205, 150)),
                  ("Armor", stats.get("armor", 0), (235, 205, 150)),
                  ("Crit", f"{stats.get('crit_chance', 0):.1f}%", (235, 205, 150)),
                  ("Dodge", f"{stats.get('dodge_chance', 0):.1f}%", (235, 205, 150))]
        for lbl, val, col in combat:
            draw.text((rx + 22, sy), lbl, fill=(220, 210, 200), font=fonts["stat_lbl"])
            draw.text((rx + half - 30, sy - 2), str(val), fill=col, font=fonts["stat_val"], anchor="ra")
            sy += 32

        y += panel_h + 20

        # ── Equipment list + footer info like reference ─────────────────────
        self._draw_panel(draw, [MARGIN, y, W - MARGIN, y + 220], fill="#141316", border="#3c2b17", radius=14)
        draw.text((MARGIN + 16, y + 12), "Equipment", fill=(235, 205, 150), font=fonts["header"])

        equipped = character_data.get("equipped", {}) or {}
        gear_slots = ["chest", "main_hand", "feet"]
        rarity_colors = {
            "common": (157, 157, 157), "uncommon": (30, 255, 0),
            "rare": (0, 112, 221), "epic": (163, 53, 238), "legendary": (255, 128, 0),
            "artifact": (255, 215, 0),
        }
        gy = y + 54
        for slot in gear_slots:
            if slot in equipped:
                item = equipped[slot]
                rarity = (item.get("rarity") or "common").lower()
                color = rarity_colors.get(rarity, (200, 200, 200))
                draw.text((MARGIN + 24, gy), f"• {item.get('name','?')}", fill=color, font=fonts["body"])
                gy += 30

        # Zone + gold like reference
        zone_key = character_data.get("current_zone", "elwynn_forest")
        zone = ZONES.get(zone_key)
        zone_name = zone.name if zone else zone_key.replace("_", " ").title()
        gold = int(character_data.get("gold", 0) or 0)
        draw.text((MARGIN + 22, y + 150), f"🌼  {zone_name}", fill=(235, 205, 150), font=fonts["body"])
        draw.text((MARGIN + 22, y + 180), f"🪙  Gold: {gold:,}", fill=(235, 205, 150), font=fonts["body"])

        # Flavor + passive (bottom)
        if spec:
            draw.text((MARGIN + 22, y + 212), f"“{spec.flavor}”", fill=(190, 185, 170), font=fonts["small"])

        # Convert to RGB for PNG
        final = Image.new("RGB", (W, H), (12, 13, 18))
        final.paste(card, mask=card.split()[3] if card.mode == "RGBA" else None)

        img_bytes = BytesIO()
        final.save(img_bytes, format="PNG", quality=95)
        img_bytes.seek(0)
        return img_bytes
