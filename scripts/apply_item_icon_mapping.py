#!/usr/bin/env python3
"""
Copy/rename item PNGs from mmorpg-web (or any folder) into activity/public/assets/items/
using a small CSV mapping file.

Mapping CSV (header required):
  source,template_id

- source: filename in --source-dir (e.g. iron_sword.png or iron_sword)
- template_id: UUID from item_templates.id (same as manifest export)

Example mapping.csv:
  source,template_id
  iron_sword.png,a1b2c3d4-e5f6-7890-abcd-ef1234567890
  health_potion.png,b2c3d4e5-f6a7-8901-bcde-f12345678901

Usage:
  python3 scripts/apply_item_icon_mapping.py \\
    --source ~/mmorpg-web/public/items \\
    --mapping mapping.csv \\
    --dest activity/public/assets/items
"""
from __future__ import annotations

import argparse
import csv
import re
import shutil
import sys
from pathlib import Path

UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.I,
)


def main() -> int:
    p = argparse.ArgumentParser(description="Apply item icon mapping into Activity public folder.")
    p.add_argument("--source", required=True, type=Path, help="Folder containing source PNGs")
    p.add_argument("--mapping", required=True, type=Path, help="CSV with columns: source,template_id")
    p.add_argument(
        "--dest",
        type=Path,
        default=Path("activity/public/assets/items"),
        help="Target folder (default: activity/public/assets/items)",
    )
    args = p.parse_args()

    if not args.source.is_dir():
        print(f"Not a directory: {args.source}", file=sys.stderr)
        return 1
    if not args.mapping.is_file():
        print(f"Mapping file not found: {args.mapping}", file=sys.stderr)
        return 1

    args.dest.mkdir(parents=True, exist_ok=True)

    with open(args.mapping, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            print("CSV is empty", file=sys.stderr)
            return 1
        cols = {c.lower().strip(): c for c in reader.fieldnames}
        for key in ("source", "template_id"):
            if key not in cols:
                print(
                    f"CSV must have columns 'source' and 'template_id'. Found: {reader.fieldnames}",
                    file=sys.stderr,
                )
                return 1
        scol, tcol = cols["source"], cols["template_id"]

        n_ok = 0
        n_miss = 0
        for row in reader:
            src_name = (row.get(scol) or "").strip()
            tid = (row.get(tcol) or "").strip()
            if not src_name or not tid:
                continue
            if not UUID_RE.match(tid):
                print(f"Skip bad template_id: {tid!r}", file=sys.stderr)
                continue

            src_path = args.source / src_name
            if not src_path.is_file() and not src_name.lower().endswith(".png"):
                alt = args.source / f"{src_name}.png"
                if alt.is_file():
                    src_path = alt

            if not src_path.is_file():
                print(f"Missing source: {src_name} (looked under {args.source})", file=sys.stderr)
                n_miss += 1
                continue

            dst = args.dest / f"{tid}.png"
            shutil.copy2(src_path, dst)
            print(f"OK {src_path.name} → {dst.name}")
            n_ok += 1

    print(f"Done. Copied {n_ok} file(s). Missing: {n_miss}")
    return 0 if n_miss == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
