#!/usr/bin/env python3
"""
Regenerate quest-VN NPC portrait PNGs under activity/public/assets/npcs/.

Uses NPC_TEMPLATES (name, title, discovery_hint) for hues and on-image labels.
Output is illustrative (soft bust silhouette + lighting), not AI-painted art.
For a full illustrated pass, use scripts/v0_prompts_npcs_quest_vn.md in v0.

Run from repo root:
  PYTHONPATH=. python3 scripts/render_npc_quest_portraits.py
"""

from __future__ import annotations

import colorsys
import hashlib
import os
import random
import re
import sys

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUT_DIR = os.path.join(ROOT, "activity", "public", "assets", "npcs")
W, H = 384, 512


def _strip_emoji(s: str) -> str:
    # crude strip for subtitle lines (Pillow default font lacks color emoji)
    return re.sub(r"[\U00010000-\U0010ffff]", "", s).strip()


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "/System/Library/Fonts/Supplemental/Cinzel-Regular.ttf",
        "/System/Library/Fonts/Supplemental/Georgia.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for p in candidates:
        if os.path.isfile(p):
            try:
                return ImageFont.truetype(p, size)
            except OSError:
                continue
    return ImageFont.load_default()


def _hue(npc_id: str) -> float:
    h = int(hashlib.sha256(npc_id.encode()).hexdigest()[:8], 16)
    return (h % 360) / 360.0


def render_one(npc_id: str, name: str, title: str, hint: str) -> Image.Image:
    hue = _hue(npc_id)
    c1 = colorsys.hsv_to_rgb(hue, 0.32, 0.14)
    c2 = colorsys.hsv_to_rgb((hue + 0.06) % 1.0, 0.38, 0.22)
    c3 = colorsys.hsv_to_rgb((hue + 0.12) % 1.0, 0.25, 0.32)
    top_rgb = tuple(int(x * 255) for x in c1)
    mid_rgb = tuple(int(x * 255) for x in c2)
    rim_rgb = tuple(int(x * 255) for x in c3)

    img = Image.new("RGB", (W, H), top_rgb)
    px = img.load()
    for y in range(H):
        t = y / max(H - 1, 1)
        r = int(top_rgb[0] * (1 - t) + mid_rgb[0] * t)
        g = int(top_rgb[1] * (1 - t) + mid_rgb[1] * t)
        b = int(top_rgb[2] * (1 - t) + mid_rgb[2] * t)
        for x in range(W):
            px[x, y] = (r, g, b)

    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    dr = ImageDraw.Draw(layer)

    cx, cy = W // 2, int(H * 0.38)
    rx, ry = int(W * 0.34), int(H * 0.38)
    dr.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], fill=(*mid_rgb, 210))
    # shoulders
    pts = [
        (cx - int(W * 0.48), cy + int(H * 0.08)),
        (cx + int(W * 0.48), cy + int(H * 0.08)),
        (cx + int(W * 0.55), H - int(H * 0.22)),
        (cx - int(W * 0.55), H - int(H * 0.22)),
    ]
    dr.polygon(pts, fill=(*top_rgb, 200))

    layer = layer.filter(ImageFilter.GaussianBlur(radius=6))
    img.paste(layer.convert("RGB"), (0, 0), layer.split()[3])

    # rim light arc
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gdr = ImageDraw.Draw(glow)
    for i in range(3):
        gdr.arc(
            [8 - i * 4, 8 - i * 4, W - 8 + i * 4, int(H * 0.72) + i * 4],
            start=200,
            end=340,
            fill=(*rim_rgb, 90 - i * 25),
            width=10,
        )
    glow = glow.filter(ImageFilter.GaussianBlur(radius=8))
    img = Image.alpha_composite(img.convert("RGBA"), glow).convert("RGB")

    dr2 = ImageDraw.Draw(img)
    footer_h = int(H * 0.22)
    dr2.rectangle([0, H - footer_h, W, H], fill=(12, 14, 22))
    dr2.line([0, H - footer_h, W, H - footer_h], fill=(55, 62, 88), width=1)

    font_title = _font(17)
    font_sub = _font(12)
    font_hint = _font(10)
    title_clean = _strip_emoji(title) or "NPC"
    name_s = name.strip() or npc_id.replace("_", " ").title()

    y0 = H - footer_h + 12
    dr2.text((16, y0), name_s, fill=(235, 238, 248), font=font_title)
    dr2.text((16, y0 + 26), title_clean[:52], fill=(160, 170, 195), font=font_sub)
    hint_wrapped = (hint or "").replace("\n", " ")
    if len(hint_wrapped) > 120:
        hint_wrapped = hint_wrapped[:117] + "…"
    dr2.text((16, y0 + 48), hint_wrapped, fill=(110, 120, 145), font=font_hint)

    # subtle film grain
    rnd = random.Random(npc_id)
    gpx = img.load()
    for _ in range(9000):
        x, y = rnd.randint(0, W - 1), rnd.randint(0, int(H * 0.78))
        r, g, b = gpx[x, y]
        j = rnd.randint(-10, 10)
        gpx[x, y] = (max(0, min(255, r + j)), max(0, min(255, g + j)), max(0, min(255, b + j)))

    return img


def write_v0_markdown(path: str, templates: dict[str, dict]) -> None:
    global_style = (
        "2D anime/chibi fantasy RPG NPC portrait illustration, waist-up only "
        "(from waist to head), 3/4 camera view, clean line art, soft cel shading, "
        "crisp silhouette, transparent background PNG. **NPC stands on the LEFT side "
        "of the canvas facing RIGHT** toward the center (quest dialogue layout). "
        "Readable at small width in a game UI portrait slot. "
        "Negative: no UI frame, no text, no watermark, no logo, no busy background scene, "
        "no photorealism, no 3D render, no blur, no extra limbs, no cropped face."
    )
    lines = [
        "# v0 prompts — quest NPC portraits (VN modal, waist-up)",
        "",
        "One prompt per NPC. Filename after export: `activity/public/assets/npcs/{npc_id}.png`.",
        "",
        "## Global style (prepend or merge into every prompt)",
        "",
        global_style,
        "",
        "---",
        "",
    ]
    for npc_id in sorted(templates.keys()):
        npc = templates[npc_id]
        name = npc.get("name") or npc_id
        title = npc.get("title") or ""
        hint = (npc.get("discovery_hint") or "").replace("\n", " ").strip()
        lines.append(f"## {npc_id} — {name}")
        lines.append("")
        lines.append(
            f"{global_style} Character: **{name}** ({title}). "
            f"Visual cues from lore: {hint}"
        )
        lines.append("")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def main() -> None:
    sys.path.insert(0, ROOT)
    from services.quest.npc_quest_service import NPC_TEMPLATES

    os.makedirs(OUT_DIR, exist_ok=True)
    md_path = os.path.join(ROOT, "scripts", "v0_prompts_npcs_quest_vn.md")
    write_v0_markdown(md_path, NPC_TEMPLATES)

    for npc_id, npc in NPC_TEMPLATES.items():
        name = str(npc.get("name") or npc_id)
        title = str(npc.get("title") or "")
        hint = str(npc.get("discovery_hint") or "")
        im = render_one(npc_id, name, title, hint)
        out = os.path.join(OUT_DIR, f"{npc_id}.png")
        im.save(out, "PNG", optimize=True)
        print("wrote", out)

    print("markdown:", md_path)


if __name__ == "__main__":
    main()
