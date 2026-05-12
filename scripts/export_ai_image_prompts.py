#!/usr/bin/env python3
"""Emit JSON of image prompts for all ENEMIES + playable CLASSES (config/settings.py)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config.settings import CLASSES, ENEMIES  # noqa: E402


def enemy_prompt(key: str, boss: bool) -> str:
    e = ENEMIES[key]
    tier = "epic zone boss" if boss else "standard zone mob"
    return (
        f"Fantasy MMORPG creature portrait, full body, {tier}: {e.name}. "
        f"Painterly game art, dramatic lighting, neutral dark gradient background, "
        f"heroic scale, readable silhouette, no text, no watermark, no UI."
    )


def class_prompt(key: str) -> str:
    c = CLASSES[key]
    return (
        f"Fantasy MMORPG playable class hero portrait waist-up: {c.name} — {c.role}. "
        f"{c.description} Painterly character art, cohesive armor or robes fitting the class, "
        f"neutral background, no text, no watermark."
    )


def main() -> None:
    enemies = []
    for key, e in ENEMIES.items():
        enemies.append(
            {
                "key": key,
                "kind": "boss" if e.is_boss else "mob",
                "display_name": e.name,
                "filename": f"enemy_{'boss' if e.is_boss else 'mob'}_{key}.png",
                "prompt": enemy_prompt(key, e.is_boss),
            }
        )
    classes = []
    for key in CLASSES:
        classes.append(
            {
                "key": key,
                "kind": "class",
                "display_name": CLASSES[key].name,
                "filename": f"class_{key}.png",
                "prompt": class_prompt(key),
            }
        )
    out = ROOT / "assets" / "ai_generated" / "image_prompts.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = {"enemies": enemies, "classes": classes, "counts": {"enemies": len(enemies), "classes": len(classes)}}
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(out)


if __name__ == "__main__":
    main()
