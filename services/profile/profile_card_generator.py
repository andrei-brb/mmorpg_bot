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

        # Render using the mapping from the v0 card component:
        # - /components/character-card.tsx (layout)
        # - /app/page.tsx (data shape)
        #
        # The React card is designed at ~420px wide and ~700px tall. We render at 703x1024
        # by scaling the 420x700 design uniformly to fit height 1024, then centering it.
        W, H = 703, 1024
        base_w, base_h = 420.0, 700.0
        s = H / base_h
        card_w = int(round(base_w * s))
        x0 = int(round((W - card_w) / 2))
        y0 = 0

        # Basic colors from the component.
        COL_BG_TOP = (42, 31, 21)     # #2a1f15
        COL_BG_MID = (26, 20, 16)     # #1a1410
        COL_BG_INNER_TOP = (31, 24, 18)  # #1f1812
        COL_BG_INNER_BOT = (21, 15, 10)  # #150f0a
        COL_GOLD = (201, 162, 39)     # #c9a227
        COL_GOLD_LIGHT = (244, 208, 63)  # #f4d03f
        COL_BROWN = (160, 128, 80)    # #a08050
        COL_PANEL = (26, 20, 16)      # #1a1410

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

        # Outer frame (p-1) + inner area (p-5) — used only for placing elements.
        p_outer = int(round(4 * s))   # p-1 = 4px
        p_inner = int(round(20 * s))  # p-5 = 20px
        inner_x1 = x0 + p_outer
        inner_y1 = y0 + p_outer
        inner_x2 = x0 + card_w - p_outer
        inner_y2 = y0 + H - p_outer

        # Inner content area (used for placement; template provides the actual visuals)
        content_x1 = inner_x1 + p_inner
        content_y1 = inner_y1 + p_inner
        content_x2 = inner_x2 - p_inner
        content_y2 = inner_y2 - p_inner
        content_w = content_x2 - content_x1
        content_h = content_y2 - content_y1

        # Fonts (scaled to match Tailwind sizes from the React component)
        def f(sz: int, *, bold: bool = True):
            # We only have one path in _load_fonts; sizes are what we control here.
            # Prefer the bold font if it exists; otherwise fallback.
            fonts = self._load_fonts()
            base_font = fonts["title"] if bold else fonts["body"]
            # Pillow can't resize a loaded font; re-load from the same file paths.
            # So we detect a usable truetype path again.
            paths = [
                "/System/Library/Fonts/Helvetica.ttc",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            ]
            font_path = next((p for p in paths if os.path.exists(p)), None)
            if font_path:
                return ImageFont.truetype(font_path, int(round(sz * s)))
            return ImageFont.load_default()

        font_name = f(24, bold=True)        # text-2xl
        font_meta = f(14, bold=True)        # text-sm font-medium
        font_special = f(14, bold=True)     # text-sm font-medium
        font_bar_label = f(14, bold=True)   # text-sm font-medium
        font_bar_val = f(12, bold=False)    # text-xs
        font_panel_title = f(14, bold=True) # text-sm font-semibold
        font_row = f(14, bold=False)        # text-sm
        font_row_val = f(14, bold=True)     # text-sm font-medium
        font_lore_label = f(14, bold=True)  # text-sm font-semibold
        font_lore = f(14, bold=False)       # text-sm italic (approx)

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

        # Core/combat stats arrays with labels like the web card expects.
        core_stats = [
            ("Strength", stats.get("strength", 0)),
            ("Agility", stats.get("agility", 0)),
            ("Intellect", stats.get("intellect", 0)),
            ("Spirit", stats.get("spirit", 0)),
            ("Stamina", stats.get("stamina", 0)),
        ]
        combat_stats = [
            ("Attack", stats.get("attack_power", 0)),
            ("Spell", stats.get("spell_power", 0)),
            ("Armor", stats.get("armor", 0)),
            ("Crit", f"{stats.get('crit_chance', 0):.1f}%"),
            ("Dodge", f"{stats.get('dodge_chance', 0):.1f}%"),
        ]

        # ── Layout mapping from components/character-card.tsx ───────────────
        # Header group: flex gap-4 mb-6; avatar w-20/h-20 border 3px
        cur_y = content_y1
        header_gap = int(round(16 * s))     # gap-4
        mb_6 = int(round(24 * s))           # mb-6
        avatar_size = int(round(80 * s))    # w-20/h-20
        avatar_border = max(1, int(round(3 * s)))

        avatar_x = content_x1
        avatar_y = cur_y
        # Avatar frame
        frame_box = [avatar_x, avatar_y, avatar_x + avatar_size, avatar_y + avatar_size]
        draw.ellipse(frame_box, fill=COL_PANEL, outline=COL_GOLD, width=avatar_border)
        # Avatar image inside
        avatar_url = character_data.get("avatar_url") or ""
        avatar = await self._fetch_image(str(avatar_url)) if avatar_url else None
        if avatar is None:
            ph = Image.new("RGBA", (avatar_size, avatar_size), (0, 0, 0, 0))
            pd = ImageDraw.Draw(ph)
            pd.ellipse([0, 0, avatar_size - 1, avatar_size - 1], fill=COL_BG_TOP + (255,))
            avatar_c = self._circle_crop(ph, avatar_size - avatar_border * 2)
        else:
            avatar_c = self._circle_crop(avatar, avatar_size - avatar_border * 2)
        card.paste(
            avatar_c,
            (avatar_x + avatar_border, avatar_y + avatar_border),
            avatar_c,
        )
        # Soft glow
        glow_ring = Image.new("RGBA", (avatar_size, avatar_size), (0, 0, 0, 0))
        gd = ImageDraw.Draw(glow_ring)
        gd.ellipse([1, 1, avatar_size - 2, avatar_size - 2], outline=(201, 162, 39, 110), width=max(1, int(round(6 * s))))
        glow_ring = glow_ring.filter(ImageFilter.GaussianBlur(radius=max(1, int(round(6 * s)))))
        card.alpha_composite(glow_ring, (avatar_x, avatar_y))
        draw = ImageDraw.Draw(card)

        # Name block to the right
        name_x = avatar_x + avatar_size + header_gap
        name_y = cur_y + int(round(4 * s))  # pt-1
        draw.text((name_x, name_y), c_name, fill=COL_GOLD, font=font_name)

        # Level | Class line (text-sm)
        meta_y = name_y + int(round(30 * s))
        meta_color = COL_BROWN
        draw.text((name_x, meta_y), f"Level {c_level}", fill=meta_color, font=font_meta)
        # separator
        sep = "|"
        sep_x = name_x + int(round(90 * s))
        draw.text((sep_x, meta_y), sep, fill=COL_GOLD, font=font_meta)
        draw.text((sep_x + int(round(14 * s)), meta_y), str(c_class), fill=meta_color, font=font_meta)

        # Specialty row with star + text (mt-2, gap-1.5)
        spec_y = meta_y + int(round(20 * s))
        star_r = max(2, int(round(7 * s)))
        star_x = name_x + star_r
        star_y = spec_y + star_r + int(round(2 * s))
        draw.ellipse([star_x - star_r, star_y - star_r, star_x + star_r, star_y + star_r], fill=COL_GOLD)
        draw.text((name_x + int(round(18 * s)), spec_y), str(c_specialty), fill=COL_GOLD, font=font_special)

        # Advance y past header
        cur_y = max(avatar_y + avatar_size, spec_y + int(round(22 * s))) + mb_6

        # Bars: h-8, mb-3 then mb-6
        bar_h = int(round(32 * s))
        bar_mb_3 = int(round(12 * s))
        bar_mb_6 = mb_6
        bar_radius = max(2, int(round(2 * s)))  # rounded-sm
        bar_border = max(1, int(round(1 * s)))
        bar_pad_x = int(round(12 * s))          # px-3

        def draw_bar(y: int, label: str, cur: int, maxv: int, c1: Tuple[int, int, int], c2: Tuple[int, int, int]):
            x1 = content_x1
            x2 = content_x2
            # track
            draw.rounded_rectangle(
                [x1, y, x2, y + bar_h],
                radius=bar_radius,
                fill=COL_PANEL,
                outline=(COL_BROWN[0], COL_BROWN[1], COL_BROWN[2], 128),
                width=bar_border,
            )
            pct = 0.0 if maxv <= 0 else max(0.0, min(1.0, float(cur) / float(maxv)))
            fill_w = int(round((x2 - x1) * pct))
            if fill_w > 0:
                fill_img = Image.new("RGBA", (fill_w, bar_h), (0, 0, 0, 0))
                self._draw_gradient_rect(fill_img, (0, 0, fill_w, bar_h), c1, c2)
                card.alpha_composite(fill_img, (x1, y))
            draw.text((x1 + bar_pad_x, y + int(round(7 * s))), label, fill=COL_GOLD, font=font_bar_label)
            val_txt = f"{cur}/{maxv}"
            bbox = draw.textbbox((0, 0), val_txt, font=font_bar_val)
            tw = bbox[2] - bbox[0]
            draw.text((x2 - bar_pad_x - tw, y + int(round(9 * s))), val_txt, fill=COL_BROWN, font=font_bar_val)

        # HP Bar
        draw_bar(cur_y, "HP", hp_cur, hp_max, (139, 0, 0), (196, 30, 58))
        cur_y += bar_h + bar_mb_3
        # Energy Bar (React component uses Energy label)
        draw_bar(cur_y, "Energy", res_cur, max(1, res_max), (30, 77, 140), (52, 152, 219))
        cur_y += bar_h + bar_mb_6

        # Stats grid: 2 columns, gap-4, each panel p-3
        grid_gap = header_gap
        panel_pad = int(round(12 * s))  # p-3
        panel_border = max(1, int(round(1 * s)))
        col_w = (content_w - grid_gap) // 2
        panel_h = int(round(220 * s))

        def draw_panel(x: int, y: int, title: str, rows: list[tuple[str, object]]):
            # panel bg and border
            draw.rounded_rectangle(
                [x, y, x + col_w, y + panel_h],
                radius=bar_radius,
                fill=(COL_PANEL[0], COL_PANEL[1], COL_PANEL[2], 140),
                outline=(COL_BROWN[0], COL_BROWN[1], COL_BROWN[2], 102),
                width=panel_border,
            )
            # title centered
            t_bbox = draw.textbbox((0, 0), title, font=font_panel_title)
            t_w = t_bbox[2] - t_bbox[0]
            draw.text((x + col_w / 2 - t_w / 2, y + panel_pad), title, fill=COL_GOLD, font=font_panel_title)

            # rows: space-y-2 (8px), each row is flex gap-2
            row_gap = int(round(8 * s))
            row_y = y + panel_pad + int(round(28 * s))
            bullet = "✦"
            for (lbl, val) in rows[:10]:
                draw.text((x + panel_pad, row_y), bullet, fill=COL_BROWN, font=font_bar_val)
                draw.text((x + panel_pad + int(round(14 * s)), row_y), str(lbl), fill=COL_BROWN, font=font_row)
                v_txt = str(val)
                vb = draw.textbbox((0, 0), v_txt, font=font_row_val)
                vw = vb[2] - vb[0]
                draw.text((x + col_w - panel_pad - vw, row_y), v_txt, fill=COL_GOLD, font=font_row_val)
                row_y += int(round(20 * s)) + row_gap

        left_x = content_x1
        right_x = content_x1 + col_w + grid_gap
        draw_panel(left_x, cur_y, "Core Stats", core_stats)
        draw_panel(right_x, cur_y, "Combat Stats", combat_stats)
        cur_y += panel_h + mb_6

        # Equipment section
        eq_title = "Equipment"
        eq_bbox = draw.textbbox((0, 0), eq_title, font=font_panel_title)
        eq_w = eq_bbox[2] - eq_bbox[0]
        draw.text((content_x1 + content_w / 2 - eq_w / 2, cur_y), eq_title, fill=COL_GOLD, font=font_panel_title)
        cur_y += int(round(24 * s))  # mb-3

        # border-t + pt-3
        draw.line([content_x1, cur_y, content_x2, cur_y], fill=(COL_BROWN[0], COL_BROWN[1], COL_BROWN[2], 80), width=panel_border)
        cur_y += panel_pad

        item_gap = int(round(8 * s))  # space-y-2
        for item in equipment_lines[:6]:
            # row with border-b
            draw.text((content_x1, cur_y), "✦", fill=COL_BROWN, font=font_bar_val)
            draw.text((content_x1 + int(round(14 * s)), cur_y), str(item), fill=COL_BROWN, font=font_row)
            # bottom border
            row_h = int(round(20 * s))
            draw.line(
                [content_x1, cur_y + row_h + int(round(6 * s)), content_x2, cur_y + row_h + int(round(6 * s))],
                fill=(COL_BROWN[0], COL_BROWN[1], COL_BROWN[2], 60),
                width=panel_border,
            )
            cur_y += row_h + item_gap

        cur_y += int(round(10 * s))

        # Lore section (mt-auto pt-4) pinned to bottom of content area
        lore_block_h = int(round(110 * s))
        lore_y = content_y2 - lore_block_h
        # Quote mark
        draw.text((content_x1, lore_y), "\"", fill=COL_GOLD, font=f(18, bold=True))
        draw.text((content_x1 + int(round(18 * s)), lore_y + int(round(2 * s))), "Lore:", fill=COL_GOLD, font=font_lore_label)
        # Lore text (simple wrap)
        lore_text = str(lore)
        max_line_w = content_w - int(round(28 * s))
        words = lore_text.split()
        lines: list[str] = []
        cur = ""
        for w in words:
            test = (cur + " " + w).strip()
            bb = draw.textbbox((0, 0), test, font=font_lore)
            if (bb[2] - bb[0]) <= max_line_w or not cur:
                cur = test
            else:
                lines.append(cur)
                cur = w
        if cur:
            lines.append(cur)
        lines = lines[:3]
        ty = lore_y + int(round(28 * s))
        for line in lines:
            draw.text((content_x1 + int(round(18 * s)), ty), line, fill=COL_BROWN, font=font_lore)
            ty += int(round(18 * s))

        final = card.convert("RGB")
        img_bytes = BytesIO()
        final.save(img_bytes, format="PNG", optimize=True)
        img_bytes.seek(0)
        return img_bytes
