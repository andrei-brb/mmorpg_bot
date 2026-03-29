#!/usr/bin/env python3
"""
Generate image-generation prompts for every combat ability (skill icon briefs).

Usage (from repo root):
  python scripts/generate_skill_icon_prompts.py
  python scripts/generate_skill_icon_prompts.py --by-class --out-file scripts/skill_icon_prompts_by_class.md
  python scripts/generate_skill_icon_prompts.py --out-dir generated/skill_icon_prompts
  python scripts/generate_skill_icon_prompts.py --format json-only

Outputs:
  - --by-class                — Markdown per class (global style + each skill’s full prompt); use --out-file to save
  - skill_icon_prompts.json   — machine-readable: key, name, emoji, prompt, filename
  - skill_icon_prompts.md     — human-readable list (when --out-dir is set)
  - <key>.txt                 — one prompt per file (optional, --split)

Requires: run from the mmorpg_bot repo so `services.combat.combat_engine` imports.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# Repo root = parent of scripts/
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.combat.combat_engine import ABILITIES  # noqa: E402

# ── Global art direction (edit to match your UI / generator) ─────────────────
ICON_STYLE = (
    "Small square MMORPG ability icon, 64x64 pixels game asset, centered symbol only, "
    "ornate thin gold and dark metal border frame, high fantasy, readable at small size, "
    "no text, no letters, no watermark, no UI chrome outside the frame, "
    "flat-shaded with subtle gradient, crisp silhouette, solid dark or parchment-like background."
)

# Themed flavor line per skill (helps the model pick coherent imagery)
SKILL_THEME: dict[str, str] = {
    "auto_attack": "simple fist or weapon swing silhouette, basic attack",
    "strike": "heavy melee swing, sword or axe impact",
    "battle_shout": "war horn or rallying burst, aggressive buff",
    "defensive_stance": "shield raised, guarded fighter stance",
    "mortal_strike": "brutal cleave, bleeding wound motif",
    "whirlwind": "spinning blades, circular slash trail",
    "colossus_smash": "hammer or strike breaking armor, cracked shield",
    "shield_slam": "shield bash, impact shock",
    "revenge": "counter slash, retaliatory strike",
    "last_stand": "heroic last stand, temporary fortitude",
    "judgment": "golden lightning hammer or holy bolt",
    "holy_light": "warm golden beam, soft radiance",
    "divine_shield": "bubble shield, divine barrier",
    "crusader_strike": "righteous weapon strike, holy spark",
    "divine_storm": "spinning holy storm, radial light",
    "hammer_of_wrath": "throwing hammer finisher, execution light",
    "holy_shock": "instant holy burst, dual damage/heal spark",
    "beacon_of_light": "candle or lighthouse motif, healing beacon",
    "lay_on_hands": "hands glowing with massive heal",
    "fireball": "classic fire sphere, embers",
    "frost_bolt": "ice shard projectile, frost trail",
    "blink": "arcane teleport swirl, motion blur",
    "pyroblast": "huge fire comet, intense blaze",
    "combustion": "self-immolation empowerment, fire aura",
    "dragon_breath": "cone of dragon flame, jaw silhouette optional",
    "ice_lance": "sharp ice spike, shard",
    "frozen_orb": "floating orb of frost shards",
    "frost_nova": "ground ice explosion, frozen ring",
    "sinister_strike": "quick dagger stab",
    "stealth": "shadow cloak, vanishing figure",
    "eviscerate": "visceral rip, deep cut",
    "mutilate": "twin daggers, twin wounds",
    "envenom": "green poison drip, venom vial",
    "vendetta": "blood mark, hunter's sigil on target",
    "shadowstrike": "strike from darkness, purple-black slash",
    "shadow_dance": "shadow afterimages, dancer motion",
    "backstab": "knife from behind, critical angle",
    "heal": "green cross or leaf-like gentle mend",
    "smite": "holy ray smiting downward",
    "power_word_shield": "blue magical barrier disc",
    "mind_blast": "psychic purple blast, brain ripple",
    "vampiric_touch": "shadow tendril draining life",
    "void_eruption": "void explosion, purple-black nova",
    "circle_of_healing": "ring of healing light, party pulse",
    "prayer_of_mending": "prayer beads, mending sparkle trail",
    "guardian_spirit": "angel wings or guardian wisp",
    "aimed_shot": "bow drawn, focused reticle",
    "multi_shot": "fan of arrows, spread shot",
    "hunters_mark": "hunter's mark symbol on target",
    "careful_aim": "spyglass or steady sight, focus buff",
    "rapid_fire": "three rapid arrow streaks",
    "double_tap": "two bullet or arrow impacts",
    "bestial_wrath": "beast rage, red eyes, fury aura",
    "dire_beast": "snarling beast silhouette pouncing",
    "kill_command": "command gesture, beast lunge",
}

# Broad class bucket for extra prompt context (not in engine; local hint only)
SKILL_CLASS: dict[str, str] = {
    "auto_attack": "general",
    "strike": "warrior",
    "battle_shout": "warrior",
    "defensive_stance": "warrior",
    "mortal_strike": "warrior",
    "whirlwind": "warrior",
    "colossus_smash": "warrior",
    "shield_slam": "warrior",
    "revenge": "warrior",
    "last_stand": "warrior",
    "judgment": "paladin",
    "holy_light": "paladin",
    "divine_shield": "paladin",
    "crusader_strike": "paladin",
    "divine_storm": "paladin",
    "hammer_of_wrath": "paladin",
    "holy_shock": "paladin",
    "beacon_of_light": "paladin",
    "lay_on_hands": "paladin",
    "fireball": "mage",
    "frost_bolt": "mage",
    "blink": "mage",
    "pyroblast": "mage",
    "combustion": "mage",
    "dragon_breath": "mage",
    "ice_lance": "mage",
    "frozen_orb": "mage",
    "frost_nova": "mage",
    "sinister_strike": "rogue",
    "stealth": "rogue",
    "eviscerate": "rogue",
    "mutilate": "rogue",
    "envenom": "rogue",
    "vendetta": "rogue",
    "shadowstrike": "rogue",
    "shadow_dance": "rogue",
    "backstab": "rogue",
    "heal": "priest",
    "smite": "priest",
    "power_word_shield": "priest",
    "mind_blast": "priest",
    "vampiric_touch": "priest",
    "void_eruption": "priest",
    "circle_of_healing": "priest",
    "prayer_of_mending": "priest",
    "guardian_spirit": "priest",
    "aimed_shot": "hunter",
    "multi_shot": "hunter",
    "hunters_mark": "hunter",
    "careful_aim": "hunter",
    "rapid_fire": "hunter",
    "double_tap": "hunter",
    "bestial_wrath": "hunter",
    "dire_beast": "hunter",
    "kill_command": "hunter",
}


def slug_filename(key: str) -> str:
    safe = re.sub(r"[^a-z0-9_]+", "_", key.lower()).strip("_")
    return f"skill_{safe}.png"


def build_prompt(key: str, ab) -> str:
    theme = SKILL_THEME.get(key, ab.description)
    cls = SKILL_CLASS.get(key, "fantasy MMORPG")
    return (
        f"{ICON_STYLE} "
        f"Class vibe: {cls}. "
        f"Ability: {ab.name}. "
        f"Visual: {theme}. "
        f"Reference mood (not text): {ab.emoji} — {ab.description}"
    )


BY_CLASS_ORDER = ("general", "warrior", "paladin", "mage", "rogue", "priest", "hunter")
BY_CLASS_LABEL = {
    "general": "Shared (all classes)",
    "warrior": "Warrior",
    "paladin": "Paladin",
    "mage": "Mage",
    "rogue": "Rogue",
    "priest": "Priest",
    "hunter": "Hunter",
}


def _abilities_by_class() -> dict[str, list[tuple[str, object]]]:
    by: dict[str, list[tuple[str, object]]] = {k: [] for k in BY_CLASS_ORDER}
    for key in ABILITIES:
        cls = SKILL_CLASS.get(key, "general")
        if cls not in by:
            cls = "general"
        by[cls].append((key, ABILITIES[key]))
    return by


def render_by_class_markdown() -> str:
    """Markdown grouped by class: global style once, then each skill with filename + full prompt."""
    by = _abilities_by_class()
    lines = [
        "# Skill icon prompts (by class)",
        "",
        "Use **Global style** once per icon (or prepend to each full prompt below).",
        "",
        "## Global style",
        "",
        ICON_STYLE,
        "",
    ]
    for cls in BY_CLASS_ORDER:
        items = sorted(by[cls], key=lambda x: x[0])
        if not items:
            continue
        lines.append(f"## {BY_CLASS_LABEL[cls]}")
        lines.append("")
        for key, ab in items:
            lines.append(f"### {ab.name} — `{key}` → `{slug_filename(key)}`")
            lines.append("")
            lines.append(build_prompt(key, ab))
            lines.append("")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description="Skill icon prompt generator for MMORPG abilities.")
    ap.add_argument(
        "--by-class",
        action="store_true",
        help="Emit Markdown grouped by class (global style once, then every skill).",
    )
    ap.add_argument(
        "--out-file",
        type=Path,
        default=None,
        help="With --by-class, write to this path instead of printing to stdout.",
    )
    ap.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="Write JSON, Markdown, and optional per-skill .txt files here.",
    )
    ap.add_argument(
        "--split",
        action="store_true",
        help="With --out-dir, also write one <key>.txt per ability.",
    )
    ap.add_argument(
        "--format",
        choices=("all", "json-only"),
        default="all",
        help="json-only prints JSON to stdout only.",
    )
    args = ap.parse_args()

    if args.by_class:
        text = render_by_class_markdown()
        if args.out_file:
            args.out_file.parent.mkdir(parents=True, exist_ok=True)
            args.out_file.write_text(text, encoding="utf-8")
            print(f"Wrote {args.out_file} ({len(text)} bytes).", file=sys.stderr)
        else:
            print(text)
        return

    rows = []
    for key in sorted(ABILITIES.keys()):
        ab = ABILITIES[key]
        prompt = build_prompt(key, ab)
        rows.append(
            {
                "key": key,
                "name": ab.name,
                "emoji": ab.emoji,
                "description": ab.description,
                "class_hint": SKILL_CLASS.get(key, ""),
                "suggested_filename": slug_filename(key),
                "prompt": prompt,
            }
        )

    payload = {
        "style_block": ICON_STYLE,
        "count": len(rows),
        "abilities": rows,
    }

    if args.format == "json-only":
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return

    if args.out_dir is None:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        print("\n# Tip: pass --out-dir generated/skill_icon_prompts to save files.", file=sys.stderr)
        return

    out = args.out_dir
    out.mkdir(parents=True, exist_ok=True)

    json_path = out / "skill_icon_prompts.json"
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    md_lines = [
        "# Skill icon generation prompts",
        "",
        f"Total abilities: **{len(rows)}**",
        "",
        "## Global style (prepend to any custom prompt)",
        "",
        f"> {ICON_STYLE}",
        "",
        "## Per-skill",
        "",
    ]
    for r in rows:
        md_lines.append(f"### {r['name']} (`{r['key']}`)")
        md_lines.append(f"- File: `{r['suggested_filename']}`")
        md_lines.append(f"- {r['prompt']}")
        md_lines.append("")
    (out / "skill_icon_prompts.md").write_text("\n".join(md_lines), encoding="utf-8")

    if args.split:
        sub = out / "prompts"
        sub.mkdir(exist_ok=True)
        for r in rows:
            (sub / f"{r['key']}.txt").write_text(r["prompt"], encoding="utf-8")

    print(f"Wrote {json_path} and skill_icon_prompts.md ({len(rows)} skills).", file=sys.stderr)
    if args.split:
        print(f"Wrote per-key .txt under {out / 'prompts'}.", file=sys.stderr)


if __name__ == "__main__":
    main()
