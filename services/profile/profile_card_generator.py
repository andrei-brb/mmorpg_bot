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

        # Use the provided blank template as the background/frame.
        # We keep our original "overlay coordinate system" (700x1050) and scale it to match the template.
        W0, H0 = 700, 1050
        template_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "../../assets/profile_card_template_blank.png")
        )
        if not os.path.exists(template_path):
            log.warning("Profile card template not found: %s", template_path)
            # Fallback: keep a transparent canvas.
            card = Image.new("RGBA", (W0, H0), (0, 0, 0, 0))
            W, H = W0, H0
        else:
            base = Image.open(template_path).convert("RGBA")
            card = base.copy()
            W, H = base.size
            # WARNING so it shows up even if INFO logs are filtered in production.
            log.warning(
                "PROFILE_CARD_TEMPLATE_USED template=%s size=%sx%s",
                os.path.basename(template_path),
                W,
                H,
            )

        # Scale factors for mapping 700x1050 coordinates onto template resolution.
        scale_x = W / W0
        scale_y = H / H0

        def sx(x: int) -> int:
            return int(round(x * scale_x))

        def sy(y: int) -> int:
            return int(round(y * scale_y))

        # X-only layout values (based on our previous generator coordinates).
        MARGIN = sx(40)
        INNER = W - 2 * MARGIN

        draw = ImageDraw.Draw(card)
        fonts = self._load_fonts()

        # ── Class / spec info ──────────────────────────────────────────────
        class_key = character_data.get("class", "warrior")
        cls = CLASSES.get(class_key)
        spec_key = character_data.get("specialization")
        spec = SPECIALIZATIONS.get(spec_key) if spec_key else None

        # ── Avatar circle (top-left) ───────────────────────────────────────
        avatar_url = character_data.get("avatar_url") or ""
        avatar = await self._fetch_image(str(avatar_url)) if avatar_url else None
        av_size = min(sx(110), sy(110))
        av_x, av_y = sx(70), sy(92)  # center point in template coordinates

        if avatar is None:
            ph = Image.new("RGBA", (av_size, av_size), (30, 30, 34, 255))
            pd = ImageDraw.Draw(ph)
            pd.ellipse([0, 0, av_size - 1, av_size - 1], fill=(28, 28, 30, 255))
            avatar_c = self._circle_crop(ph, av_size)
        else:
            avatar_c = self._circle_crop(avatar, av_size)

        card.paste(
            avatar_c,
            (av_x - av_size // 2, av_y - av_size // 2),
            avatar_c,
        )
        draw = ImageDraw.Draw(card)

        # ── Header text (right of avatar) ──────────────────────────────────
        char_name = character_data.get("name", "Unknown")
        level = character_data.get("level", 1)
        cls_name = cls.name if cls else class_key.title()
        spec_line = f"★ {spec.name} Specialist" if spec else ""

        name_x = sx(150)
        draw.text((name_x, sy(60)), str(char_name), fill=(240, 210, 150), font=fonts["title"])
        draw.text(
            (name_x, sy(104)),
            f"Level {level} {cls_name}",
            fill=(180, 210, 160),
            font=fonts["subtitle"],
        )
        if spec_line:
            draw.text((name_x, sy(136)), spec_line, fill=(200, 190, 150), font=fonts["body"])

        # thin separator (template already has one, but this is a safe low-impact overlay)
        y = sy(180)
        draw.line([MARGIN, y, W - MARGIN, y], fill=(120, 95, 55), width=1)
        y += sy(18)

        # ── HP & Resource bars (only fill + values; frame/tracks come from template) ──
        def draw_bar_fill(value: int, maximum: int, y0: int, color: Tuple[int, int, int]):
            bar_h = sy(30)
            bar_x = MARGIN + sx(40)
            bar_w = INNER - sx(40)
            # Matches the inner track coordinates from the previous generator.
            ty = y0 + sy(10)

            pct = 0.0 if maximum <= 0 else max(0.0, min(1.0, float(value) / float(maximum)))
            fw = int((bar_w - 2) * pct)

            if fw > 0:
                radius = max(2, min(sx(9), sy(9)))
                draw.rounded_rectangle(
                    [bar_x + 1, ty + 1, bar_x + 1 + fw, ty + bar_h - sy(11)],
                    radius=radius,
                    fill=color,
                )

            txt = f"{int(value):,} / {int(maximum):,}"
            bbox = draw.textbbox((0, 0), txt, font=fonts["bar_text"])
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]
            draw.text(
                (bar_x + bar_w / 2 - tw / 2, ty + sy(2)),
                txt,
                fill=(255, 240, 220),
                font=fonts["bar_text"],
            )

        current_hp = int(character_data.get("current_hp", 0) or 0)
        max_hp = int(character_data.get("max_hp", 1) or 1)
        draw_bar_fill(current_hp, max_hp, y, (200, 55, 55))
        y += sy(70)

        max_res = int(character_data.get("max_res", 0) or 0)
        current_res = int(character_data.get("current_res", 0) or 0)
        res_type = character_data.get("res_type", "mana")
        res_color = {"mana": (70, 120, 220), "energy": (240, 180, 40), "rage": (200, 55, 55)}.get(
            res_type, (200, 160, 80)
        )
        if max_res > 0:
            draw_bar_fill(current_res, max_res, y, res_color)
            y += sy(78)
        else:
            y += sy(10)

        # ── Stats panels (values only; template provides the framing) ──
        y += sy(6)
        panel_h = sy(220)
        half = (INNER - sx(18)) // 2
        lx = MARGIN
        rx = MARGIN + half + sx(18)

        core_sy = y + sy(54)
        core = [
            ("STR", stats.get("strength", 0), (220, 190, 120)),
            ("AGI", stats.get("agility", 0), (120, 220, 120)),
            ("INT", stats.get("intellect", 0), (120, 180, 240)),
            ("SPI", stats.get("spirit", 0), (180, 120, 240)),
            ("STA", stats.get("stamina", 0), (220, 120, 120)),
        ]
        for lbl, val, col in core:
            draw.text((lx + sx(22), core_sy), lbl, fill=(220, 210, 200), font=fonts["stat_lbl"])
            draw.text(
                (lx + half - sx(30), core_sy - sy(2)),
                str(val),
                fill=col,
                font=fonts["stat_val"],
                anchor="ra",
            )
            core_sy += sy(32)

        combat_sy = y + sy(54)
        combat = [
            ("Attack", stats.get("attack_power", 0), (235, 205, 150)),
            ("Spell", stats.get("spell_power", 0), (235, 205, 150)),
            ("Armor", stats.get("armor", 0), (235, 205, 150)),
            ("Crit", f"{stats.get('crit_chance', 0):.1f}%", (235, 205, 150)),
            ("Dodge", f"{stats.get('dodge_chance', 0):.1f}%", (235, 205, 150)),
        ]
        for lbl, val, col in combat:
            draw.text((rx + sx(22), combat_sy), lbl, fill=(220, 210, 200), font=fonts["stat_lbl"])
            draw.text(
                (rx + half - sx(30), combat_sy - sy(2)),
                str(val),
                fill=col,
                font=fonts["stat_val"],
                anchor="ra",
            )
            combat_sy += sy(32)

        y += panel_h + sy(20)

        # ── Equipment list + footer (template already has layout) ──
        equipped = character_data.get("equipped", {}) or {}
        gear_slots = ["chest", "main_hand", "feet"]
        rarity_colors = {
            "common": (157, 157, 157),
            "uncommon": (30, 255, 0),
            "rare": (0, 112, 221),
            "epic": (163, 53, 238),
            "legendary": (255, 128, 0),
            "artifact": (255, 215, 0),
        }

        gy = y + sy(54)
        for slot in gear_slots:
            if slot not in equipped:
                continue
            item = equipped[slot]
            rarity = (item.get("rarity") or "common").lower()
            color = rarity_colors.get(rarity, (200, 200, 200))
            name = item.get("name", "?")

            # Names only (no extra icons), aligned where the name used to start.
            draw.text((MARGIN + sx(62), gy), str(name), fill=color, font=fonts["body"])
            gy += sy(30)

        # Zone + gold
        zone_key = character_data.get("current_zone", "elwynn_forest")
        zone = ZONES.get(zone_key)
        zone_name = zone.name if zone else zone_key.replace("_", " ").title()
        gold = int(character_data.get("gold", 0) or 0)
        zone_emoji = zone.emoji if zone else "🗺️"
        draw.text(
            (MARGIN + sx(22), y + sy(150)),
            f"{zone_emoji}  {zone_name}",
            fill=(235, 205, 150),
            font=fonts["body"],
        )
        draw.text(
            (MARGIN + sx(22), y + sy(180)),
            f"🪙  Gold: {gold:,}",
            fill=(235, 205, 150),
            font=fonts["body"],
        )

        # Flavor + passive
        if spec:
            draw.text(
                (MARGIN + sx(22), y + sy(208)),
                f"“{spec.flavor}”",
                fill=(190, 185, 170),
                font=fonts["small"],
            )
            passive = f"{spec.emoji} {spec.passive_desc}"
            draw.text(
                (MARGIN + sx(22), y + sy(236)),
                passive,
                fill=(200, 205, 215),
                font=fonts["small"],
            )

        # Convert to RGB for PNG output.
        final = card.convert("RGB")
        img_bytes = BytesIO()
        final.save(img_bytes, format="PNG", optimize=True)
        img_bytes.seek(0)
        return img_bytes
