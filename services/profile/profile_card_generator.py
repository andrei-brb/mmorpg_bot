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

try:
    import aiohttp
except ModuleNotFoundError:  # pragma: no cover
    aiohttp = None
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance

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
        if aiohttp is None:
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

        # Render using the ornate 703x1024 template and a pixel-accurate mapping.
        W, H = 703, 1024
        COL_GOLD = (212, 175, 55)
        COL_TEXT = (230, 200, 140)
        COL_MUTED = (175, 150, 110)
        COL_SHADOW = (10, 8, 6, 160)

        # Use the provided ornate template as the background.
        template_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "../../assets/profile_card_template_final.png")
        )
        if os.path.exists(template_path):
            base = Image.open(template_path).convert("RGBA")
            if base.size != (W, H):
                base = base.resize((W, H), Image.Resampling.LANCZOS)
            card = base.copy()
            log.warning(
                "PROFILE_CARD_TEMPLATE_USED template=%s size=%sx%s",
                os.path.basename(template_path),
                W,
                H,
            )
        else:
            log.warning("Profile card template not found: %s", template_path)
            card = Image.new("RGBA", (W, H), (0, 0, 0, 255))
            self._draw_gradient_rect(card, (0, 0, W, H), (10, 8, 6), (8, 6, 5))
        draw = ImageDraw.Draw(card)

        # Fonts sized for 703x1024 template
        def f(sz: int):
            paths = [
                "/System/Library/Fonts/Times.ttc",
                "/System/Library/Fonts/Helvetica.ttc",
                "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            ]
            font_path = next((p for p in paths if os.path.exists(p)), None)
            if font_path:
                return ImageFont.truetype(font_path, sz)
            return ImageFont.load_default()

        font_name = f(44)
        font_meta = f(26)
        font_special = f(28)
        font_bar_val = f(20)
        font_stat_lbl = f(20)
        font_stat_val = f(22)
        font_item = f(22)
        font_lore = f(22)

        # ── Data mapping (matches /app/page.tsx shape) ─────────────────────
        class_key = character_data.get("class", "warrior")
        cls = CLASSES.get(class_key)
        spec_key = character_data.get("specialization")
        spec = SPECIALIZATIONS.get(spec_key) if spec_key else None

        c_name = str(character_data.get("name", "Character Name"))
        c_level = int(character_data.get("level", 1) or 1)
        c_class = (cls.name if cls else str(class_key).title())
        c_specialty = spec.name if spec else (character_data.get("specialty") or "Specialty")

        hp_cur = int(character_data.get("current_hp", 0) or 0)
        hp_max = int(character_data.get("max_hp", 1) or 1)
        res_cur = int(character_data.get("current_res", 0) or 0)
        res_max = int(character_data.get("max_res", 0) or 0)

        equipped = character_data.get("equipped", {}) or {}
        gear_slots = ["chest", "main_hand", "feet"]
        equipment_lines = []
        for slot in gear_slots:
            item = equipped.get(slot)
            if not item:
                continue
            equipment_lines.append(str(item.get("name") or ""))
        equipment_lines = [x for x in equipment_lines if x][:3]
        if not equipment_lines:
            equipment_lines = ["—"]

        # Lore: use specialization flavor if present; else fall back.
        lore = ""
        if spec:
            lore = spec.flavor
            if getattr(spec, "passive_desc", None):
                lore = f"{lore} {spec.passive_desc}"
        lore = lore or str(character_data.get("lore") or "...")

        # Template-native layout coordinates (measured from the 703x1024 image)
        AVATAR_BBOX = (11, 14, 259, 259)
        NAME_POS = (270, 56)
        META_POS = (270, 120)
        SPEC_POS = (270, 170)

        HP_BORDER = (88, 253, 646, 339)
        EN_BORDER = (88, 313, 646, 417)
        HP_FILL = (110, 288, 636, 315)
        EN_FILL = (110, 350, 636, 377)

        CORE_ROWS_Y = [472, 515, 558, 600]
        CORE_LABEL_X = 138
        CORE_VALUE_X = 300

        COMBAT_ROWS_Y = [472, 515, 558, 600]
        COMBAT_LABEL_X = 435
        COMBAT_VALUE_X = 615

        EQUIP_ROWS_Y = [705, 767, 829]
        EQUIP_TEXT_X = 130

        LORE_POS = (96, 948)

        # Mask placeholder header so the real text is readable
        draw.rectangle([250, 35, 680, 215], fill=COL_SHADOW)

        # Avatar
        avatar_url = character_data.get("avatar_url") or ""
        avatar = await self._fetch_image(str(avatar_url)) if avatar_url else None
        ax1, ay1, ax2, ay2 = AVATAR_BBOX
        av_d = min(ax2 - ax1, ay2 - ay1) - 22
        if avatar is None:
            ph = Image.new("RGBA", (av_d, av_d), (30, 30, 34, 255))
            pd = ImageDraw.Draw(ph)
            pd.ellipse([0, 0, av_d - 1, av_d - 1], fill=(28, 28, 30, 255))
            avatar_c = self._circle_crop(ph, av_d)
        else:
            avatar_c = self._circle_crop(avatar, av_d)
        card.paste(avatar_c, (ax1 + 11, ay1 + 11), avatar_c)

        # Header text
        draw.text(NAME_POS, c_name, fill=COL_TEXT, font=font_name)
        draw.text(META_POS, f"Level {c_level}  |  {c_class}", fill=COL_MUTED, font=font_meta)
        draw.text(SPEC_POS, f"★ {c_specialty}", fill=COL_TEXT, font=font_special)

        # Bars: fill + values
        def fill_bar(fill_box, cur, maxv, color):
            x1, y1, x2, y2 = fill_box
            pct = 0.0 if maxv <= 0 else max(0.0, min(1.0, float(cur) / float(maxv)))
            w = int(round((x2 - x1) * pct))
            if w > 0:
                draw.rectangle([x1, y1, x1 + w, y2], fill=color)

        fill_bar(HP_FILL, hp_cur, hp_max, (196, 30, 58, 255))
        fill_bar(EN_FILL, res_cur, max(1, res_max), (52, 152, 219, 255))

        hp_txt = f"{hp_cur}/{hp_max}"
        en_txt = f"{res_cur}/{res_max}"
        hb = draw.textbbox((0, 0), hp_txt, font=font_bar_val)
        eb = draw.textbbox((0, 0), en_txt, font=font_bar_val)
        draw.text(
            (HP_BORDER[2] - 12 - (hb[2] - hb[0]), HP_FILL[1] - 24),
            hp_txt,
            fill=COL_MUTED,
            font=font_bar_val,
        )
        draw.text(
            (EN_BORDER[2] - 12 - (eb[2] - eb[0]), EN_FILL[1] - 24),
            en_txt,
            fill=COL_MUTED,
            font=font_bar_val,
        )

        # Stats: template has 4 rows each
        core_rows = [
            ("Strength", stats.get("strength", 0)),
            ("Agility", stats.get("agility", 0)),
            ("Intellect", stats.get("intellect", 0)),
            ("Stamina", stats.get("stamina", 0)),
        ]
        combat_rows = [
            ("Attack", stats.get("attack_power", 0)),
            ("Armor", stats.get("armor", 0)),
            ("Crit", f"{stats.get('crit_chance', 0):.1f}%"),
            ("Dodge", f"{stats.get('dodge_chance', 0):.1f}%"),
        ]

        draw.rectangle([105, 430, 640, 640], fill=(10, 8, 6, 110))

        for y, (lbl, val) in zip(CORE_ROWS_Y, core_rows):
            draw.text((CORE_LABEL_X, y), str(lbl), fill=COL_MUTED, font=font_stat_lbl)
            v = str(val)
            vb = draw.textbbox((0, 0), v, font=font_stat_val)
            draw.text((CORE_VALUE_X - (vb[2] - vb[0]), y - 2), v, fill=COL_TEXT, font=font_stat_val)

        for y, (lbl, val) in zip(COMBAT_ROWS_Y, combat_rows):
            draw.text((COMBAT_LABEL_X, y), str(lbl), fill=COL_MUTED, font=font_stat_lbl)
            v = str(val)
            vb = draw.textbbox((0, 0), v, font=font_stat_val)
            draw.text((COMBAT_VALUE_X - (vb[2] - vb[0]), y - 2), v, fill=COL_TEXT, font=font_stat_val)

        # Equipment
        draw.rectangle([105, 680, 640, 860], fill=(10, 8, 6, 95))
        for y, item in zip(EQUIP_ROWS_Y, equipment_lines[:3]):
            draw.text((EQUIP_TEXT_X, y), str(item), fill=COL_MUTED, font=font_item)

        # Lore bottom line
        lore_text = str(lore).strip()
        if len(lore_text) > 60:
            lore_text = lore_text[:57].rsplit(" ", 1)[0] + "..."
        draw.text(LORE_POS, lore_text, fill=COL_MUTED, font=font_lore)

        final = card.convert("RGB")
        img_bytes = BytesIO()
        final.save(img_bytes, format="PNG", optimize=True)
        img_bytes.seek(0)
        return img_bytes
