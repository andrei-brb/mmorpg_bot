#!/usr/bin/env python3
"""
Export item_templates → CSV so you can match mmorpg-web filenames to Activity icon names.

Usage (from repo root, same DATABASE_URL as the bot):
  export DATABASE_URL="postgresql://..."
  python3 scripts/export_item_icon_manifest.py
  python3 scripts/export_item_icon_manifest.py path/to/manifest.csv

Output columns: template_id, filename, name
Activity expects: activity/public/assets/items/{template_id}.png
"""
from __future__ import annotations

import asyncio
import csv
import os
import sys


async def _run(out_path: str) -> int:
    try:
        import asyncpg
    except ImportError:
        print("Install asyncpg: pip install asyncpg", file=sys.stderr)
        return 1

    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        print("Set DATABASE_URL (same as your bot).", file=sys.stderr)
        return 1

    conn = await asyncpg.connect(url)
    try:
        rows = await conn.fetch(
            "SELECT id::text AS tid, name FROM item_templates ORDER BY name"
        )
    finally:
        await conn.close()

    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["template_id", "filename", "name"])
        for r in rows:
            tid = r["tid"]
            w.writerow([tid, f"{tid}.png", r["name"]])

    print(f"Wrote {len(rows)} rows → {out_path}")
    print("Rename your mmorpg-web PNGs to match `filename`, or use scripts/apply_item_icon_mapping.py")
    return 0


def main() -> None:
    out = sys.argv[1] if len(sys.argv) > 1 else "item_template_manifest.csv"
    raise SystemExit(asyncio.run(_run(out)))


if __name__ == "__main__":
    main()
