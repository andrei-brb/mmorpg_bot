"""
Generate foundation + spec talent JSON for all classes/specs.
Run: python -m config.talents.generate_trees
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from config.settings import CLASSES, SPECIALIZATIONS

_DIR = Path(__file__).resolve().parent
_FOUNDATION_DIR = _DIR / "foundation"
_SPECS_DIR = _DIR / "specs"


def _desc_stat(stat: str, per: float, rank: int) -> str:
    total = per * rank
    labels = {
        "strength": "STR",
        "agility": "AGI",
        "intellect": "INT",
        "spirit": "SPI",
        "stamina": "STA",
        "armor": "Armor",
        "crit_pct": "Crit",
        "haste_pct": "Haste",
        "lifesteal_pct": "Lifesteal",
        "resistance": "Resistance",
    }
    return f"+{total:g} {labels.get(stat, stat)}"


def _stat_node(
    nid: str,
    name: str,
    column: int,
    tier: int,
    stat: str,
    per_rank: float,
    prereqs: List[str],
    max_ranks: int = 3,
) -> Dict[str, Any]:
    return {
        "id": nid,
        "name": name,
        "column": column,
        "tier": tier,
        "max_ranks": max_ranks,
        "node_type": "stat",
        "prereqs": prereqs,
        "effects": [{"stat": stat, "per_rank": per_rank}],
        "descriptions": [_desc_stat(stat, per_rank, r) for r in range(1, max_ranks + 1)],
    }


def _spec_passive_node(
    nid: str,
    name: str,
    column: int,
    tier: int,
    passive_key: str,
    prereqs: List[str],
    max_ranks: int = 3,
) -> Dict[str, Any]:
    return {
        "id": nid,
        "name": name,
        "column": column,
        "tier": tier,
        "max_ranks": max_ranks,
        "node_type": "spec_passive",
        "prereqs": prereqs,
        "effects": [{"passive_key": passive_key, "potency_per_rank": 0.12}],
        "descriptions": [
            f"Improves {name} ({int(100 * 0.12 * r)}% stronger)" for r in range(1, max_ranks + 1)
        ],
    }


def _proc_node(
    nid: str,
    name: str,
    column: int,
    tier: int,
    proc_id: str,
    prereqs: List[str],
    max_ranks: int = 3,
) -> Dict[str, Any]:
    return {
        "id": nid,
        "name": name,
        "column": column,
        "tier": tier,
        "max_ranks": max_ranks,
        "node_type": "proc",
        "prereqs": prereqs,
        "effects": [{"proc_id": proc_id, "chance_per_rank": 0.04}],
        "descriptions": [
            f"{name}: +{int(4 * r)}% proc chance" for r in range(1, max_ranks + 1)
        ],
    }


def _utility_node(
    nid: str,
    name: str,
    column: int,
    tier: int,
    util_key: str,
    prereqs: List[str],
    max_ranks: int = 3,
) -> Dict[str, Any]:
    return {
        "id": nid,
        "name": name,
        "column": column,
        "tier": tier,
        "max_ranks": max_ranks,
        "node_type": "utility",
        "prereqs": prereqs,
        "effects": [{"utility": util_key, "pct_per_rank": 5}],
        "descriptions": [f"{name}: +{5 * r}%" for r in range(1, max_ranks + 1)],
    }


def _capstone_node(nid: str, name: str, column: int, tier: int, prereqs: List[str], effects: List[Dict]) -> Dict[str, Any]:
    return {
        "id": nid,
        "name": name,
        "column": column,
        "tier": tier,
        "max_ranks": 1,
        "node_type": "capstone",
        "prereqs": prereqs,
        "effects": effects,
        "descriptions": [name],
    }


def _foundation_core_nodes(class_key: str) -> List[Dict[str, Any]]:
    """Lovable-style 7-node foundation grid (5 point budget) above spec previews."""
    starter = f"{class_key}_starter"
    pfx = f"{class_key}_f"
    pri = CLASSES[class_key].primary_stat
    role = CLASSES[class_key].role

    if role == "tank":
        row1 = [
            _stat_node(f"{pfx}_vigor", "Battle Vigor", 1, 1, "stamina", 2, [starter], 3),
            _stat_node(f"{pfx}_bulwark", "Bulwark", 3, 1, "armor", 5, [starter], 2),
        ]
        row1.insert(1, _stat_node(f"{pfx}_edge", "Honed Edge", 2, 1, pri, 2, [starter], 3))
        row2 = [
            _stat_node(f"{pfx}_swift", "Swift Strikes", 1, 2, "haste_pct", 3, [f"{pfx}_vigor"], 2),
            _stat_node(f"{pfx}_iron", "Iron Will", 3, 2, "resistance", 15, [f"{pfx}_bulwark"], 2),
        ]
        row2.insert(1, _stat_node(f"{pfx}_keen", "Keen Eye", 2, 2, "crit_pct", 2, [f"{pfx}_edge"], 2))
        cap = _capstone_node(
            f"{pfx}_veteran",
            "Veteran's Insight",
            2,
            3,
            [f"{pfx}_swift", f"{pfx}_keen", f"{pfx}_iron"],
            [{"utility": "combat_xp", "pct_per_rank": 10}],
        )
        cap["points_required"] = 3
        cap["node_type"] = "utility"
        cap["descriptions"] = ["+10% XP from kills"]
        return row1 + row2 + [cap]

    if role == "healer":
        row1 = [
            _stat_node(f"{pfx}_devotion", "Devotion", 1, 1, "spirit", 3, [starter], 3),
            _stat_node(f"{pfx}_clarity", "Inner Clarity", 2, 1, "intellect", 3, [starter], 3),
            _stat_node(f"{pfx}_sanctuary", "Sanctuary", 3, 1, "stamina", 2, [starter], 2),
        ]
        row2 = [
            _stat_node(f"{pfx}_mending", "Mending Touch", 1, 2, pri, 2, [f"{pfx}_devotion"], 2),
            _stat_node(f"{pfx}_ward", "Ward", 2, 2, "resistance", 12, [f"{pfx}_clarity"], 2),
            _stat_node(f"{pfx}_serenity", "Serenity", 3, 2, "spirit", 2, [f"{pfx}_sanctuary"], 2),
        ]
        cap = _capstone_node(
            f"{pfx}_beacon",
            "Beacon",
            2,
            3,
            [f"{pfx}_mending", f"{pfx}_ward", f"{pfx}_serenity"],
            [{"utility": "craft_xp", "pct_per_rank": 10}],
        )
        cap["points_required"] = 3
        cap["node_type"] = "utility"
        cap["descriptions"] = ["+10% crafting XP"]
        return row1 + row2 + [cap]

    if class_key == "mage":
        row1 = [
            _stat_node(f"{pfx}_focus", "Arcane Focus", 1, 1, "intellect", 3, [starter], 3),
            _stat_node(f"{pfx}_spark", "Kindled Spark", 2, 1, pri, 2, [starter], 3),
            _stat_node(f"{pfx}_ward", "Mana Ward", 3, 1, "resistance", 12, [starter], 2),
        ]
        row2 = [
            _stat_node(f"{pfx}_haste", "Quickened Cast", 1, 2, "haste_pct", 3, [f"{pfx}_focus"], 2),
            _stat_node(f"{pfx}_crit", "Arcane Precision", 2, 2, "crit_pct", 2, [f"{pfx}_spark"], 2),
            _stat_node(f"{pfx}_spirit", "Deep Well", 3, 2, "spirit", 2, [f"{pfx}_ward"], 2),
        ]
        cap = _capstone_node(
            f"{pfx}_mastery",
            "Spell Mastery",
            2,
            3,
            [f"{pfx}_haste", f"{pfx}_crit", f"{pfx}_spirit"],
            [{"stat": "intellect", "flat": 5}],
        )
        cap["points_required"] = 3
        cap["descriptions"] = ["+5 INT"]
        return row1 + row2 + [cap]

    # DPS / hybrid default
    row1 = [
        _stat_node(f"{pfx}_vigor", "Battle Vigor", 1, 1, "stamina", 2, [starter], 3),
        _stat_node(f"{pfx}_edge", "Honed Edge", 2, 1, pri, 2, [starter], 3),
        _stat_node(f"{pfx}_precision", "Precision", 3, 1, "crit_pct", 2, [starter], 2),
    ]
    row2 = [
        _stat_node(f"{pfx}_swift", "Swift Strikes", 1, 2, "haste_pct", 3, [f"{pfx}_vigor"], 2),
        _stat_node(f"{pfx}_lethality", "Lethality", 2, 2, pri, 2, [f"{pfx}_edge"], 2),
        _stat_node(f"{pfx}_keen", "Keen Eye", 3, 2, "crit_pct", 2, [f"{pfx}_precision"], 2),
    ]
    cap = _capstone_node(
        f"{pfx}_veteran",
        "Veteran's Insight",
        2,
        3,
        [f"{pfx}_swift", f"{pfx}_lethality", f"{pfx}_keen"],
        [{"utility": "combat_xp", "pct_per_rank": 10}],
    )
    cap["points_required"] = 3
    cap["node_type"] = "utility"
    cap["descriptions"] = ["+10% XP from kills"]
    return row1 + row2 + [cap]


def build_foundation(class_key: str) -> Dict[str, Any]:
    specs = list(CLASSES[class_key].specializations)
    starter_id = f"{class_key}_starter"
    nodes: List[Dict[str, Any]] = [
        {
            "id": starter_id,
            "name": "Foundation",
            "column": 2,
            "tier": 0,
            "max_ranks": 1,
            "node_type": "starter",
            "layer": "starter",
            "spec_key": None,
            "prereqs": [],
            "auto_grant": True,
            "effects": [{"stat": "stamina", "per_rank": 2}],
            "descriptions": ["+2 STA — every journey starts here."],
        },
    ]
    for n in _foundation_core_nodes(class_key):
        n["layer"] = "core"
        nodes.append(n)
    for i, sk in enumerate(specs):
        sp = SPECIALIZATIONS[sk]
        col = 1 if i == 0 else 3
        nodes.append(
            {
                "id": f"{class_key}_preview_{sk}",
                "name": f"{sp.name} Aptitude",
                "column": col,
                "tier": 4,
                "max_ranks": 2,
                "node_type": "preview",
                "layer": "preview",
                "spec_key": sk,
                "prereqs": [starter_id],
                "effects": [{"stat": _primary_for_class(class_key), "per_rank": 1}],
                "descriptions": [
                    f"Lean toward {sp.name} (+1 {_primary_for_class(class_key)} per rank)",
                    f"Lean toward {sp.name} (+2 {_primary_for_class(class_key)} per rank)",
                ],
            }
        )
    return {"class_key": class_key, "nodes": nodes}


def _primary_for_class(class_key: str) -> str:
    p = CLASSES[class_key].primary_stat
    return {"strength": "STR", "agility": "AGI", "intellect": "INT"}.get(p, p.upper()[:3])


def _role_templates(role: str, spec_key: str, class_key: str) -> List[Dict[str, Any]]:
    sp = SPECIALIZATIONS[spec_key]
    pfx = spec_key
    passive_key = spec_key
    pri = CLASSES[class_key].primary_stat

    if role == "tank":
        n: List[Dict[str, Any]] = []
        t0 = f"{pfx}_t0_c2"
        n.append(_stat_node(f"{pfx}_t0_c0", "Fortitude", 0, 2, "stamina", 3, [f"{class_key}_preview_{spec_key}"], 3))
        n.append(_stat_node(f"{pfx}_t0_c1", "Bulwark", 1, 2, "armor", 8, [f"{class_key}_preview_{spec_key}"], 3))
        n.append(_stat_node(t0, "Steadfast", 2, 2, pri, 2, [f"{class_key}_preview_{spec_key}"], 3))
        n.append(_stat_node(f"{pfx}_t0_c3", "Thick Hide", 3, 2, "resistance", 3, [f"{class_key}_preview_{spec_key}"], 3))
        n.append(_stat_node(f"{pfx}_t0_c4", "Guardian's Spirit", 4, 2, "spirit", 2, [f"{class_key}_preview_{spec_key}"], 3))

        t1 = [f"{pfx}_t0_c0", f"{pfx}_t0_c1", t0]
        n.append(_spec_passive_node(f"{pfx}_t1_c2", sp.passive_name, 2, 3, passive_key, t1, 3))
        n.append(_proc_node(f"{pfx}_t1_c0", "Retaliation", 0, 3, "on_block", t1, 3))
        n.append(_proc_node(f"{pfx}_t1_c4", "Last Gasp", 4, 3, "low_hp_save", t1, 2))

        t2 = [f"{pfx}_t1_c2"]
        n.append(_stat_node(f"{pfx}_t2_c1", "Iron Will", 1, 4, "stamina", 4, t2, 3))
        n.append(_stat_node(f"{pfx}_t2_c3", "Shield Training", 3, 4, "armor", 12, t2, 3))
        n.append(_utility_node(f"{pfx}_t2_c0", "Field Repairs", 0, 4, "rest_cd", t2, 2))
        n.append(_utility_node(f"{pfx}_t2_c4", "Guild Patron", 4, 4, "craft_xp", t2, 2))

        t3 = [f"{pfx}_t2_c1", f"{pfx}_t2_c3"]
        n.append(_proc_node(f"{pfx}_t3_c2", "Thunder Clap", 2, 5, "on_hit_slow", t3, 3))
        n.append(_stat_node(f"{pfx}_t3_c0", "Unyielding", 0, 5, "resistance", 5, t3, 2))

        cap_pre = [f"{pfx}_t3_c2", f"{pfx}_t1_c2"]
        n.append(
            _capstone_node(
                f"{pfx}_capstone",
                f"{sp.name} Bastion",
                2,
                6,
                cap_pre,
                [{"stat": "stamina", "flat": 15}, {"stat": "armor", "flat": 40}],
            )
        )
        return n

    if role == "healer":
        n = []
        t0 = f"{pfx}_t0_c2"
        n.append(_stat_node(f"{pfx}_t0_c0", "Devotion", 0, 2, "spirit", 3, [f"{class_key}_preview_{spec_key}"], 3))
        n.append(_stat_node(f"{pfx}_t0_c1", "Clarity", 1, 2, "intellect", 3, [f"{class_key}_preview_{spec_key}"], 3))
        n.append(_stat_node(t0, "Sanctuary", 2, 2, "stamina", 2, [f"{class_key}_preview_{spec_key}"], 3))
        n.append(_stat_node(f"{pfx}_t0_c3", "Mending", 3, 2, pri, 2, [f"{class_key}_preview_{spec_key}"], 3))
        n.append(_utility_node(f"{pfx}_t0_c4", "Offering", 4, 2, "craft_xp", [f"{class_key}_preview_{spec_key}"], 2))

        t1 = [f"{pfx}_t0_c0", t0]
        n.append(_spec_passive_node(f"{pfx}_t1_c2", sp.passive_name, 2, 3, passive_key, t1, 3))
        n.append(_proc_node(f"{pfx}_t1_c1", "Renewing Light", 1, 3, "on_heal", t1, 3))
        n.append(_proc_node(f"{pfx}_t1_c3", "Blessed Crit", 3, 3, "on_crit", t1, 2))

        t2 = [f"{pfx}_t1_c2"]
        n.append(_stat_node(f"{pfx}_t2_c0", "Spirit Well", 0, 4, "spirit", 4, t2, 3))
        n.append(_stat_node(f"{pfx}_t2_c4", "Inner Focus", 4, 4, "intellect", 3, t2, 3))
        n.append(_utility_node(f"{pfx}_t2_c1", "Restful Hours", 1, 4, "rest_cd", t2, 2))
        n.append(_stat_node(f"{pfx}_t2_c3", "Resilience", 3, 4, "resistance", 4, t2, 2))

        t3 = [f"{pfx}_t2_c0", f"{pfx}_t2_c4"]
        n.append(_proc_node(f"{pfx}_t3_c2", "Echo of Light", 2, 5, "on_heal_hot", t3, 3))
        n.append(_stat_node(f"{pfx}_t3_c1", "Hastened Prayers", 1, 5, "haste_pct", 2, t3, 2))

        n.append(
            _capstone_node(
                f"{pfx}_capstone",
                f"{sp.name} Beacon",
                2,
                6,
                [f"{pfx}_t3_c2", f"{pfx}_t1_c2"],
                [{"stat": "spirit", "flat": 12}, {"utility": "heal_power", "pct": 8}],
            )
        )
        return n

    # dps default
    n = []
    t0 = f"{pfx}_t0_c2"
    n.append(_stat_node(f"{pfx}_t0_c0", "Precision", 0, 2, pri, 3, [f"{class_key}_preview_{spec_key}"], 3))
    n.append(_stat_node(f"{pfx}_t0_c1", "Ferocity", 1, 2, "crit_pct", 1.5, [f"{class_key}_preview_{spec_key}"], 3))
    n.append(_stat_node(t0, "Killer Instinct", 2, 2, "stamina", 2, [f"{class_key}_preview_{spec_key}"], 3))
    n.append(_stat_node(f"{pfx}_t0_c3", "Quick Hands", 3, 2, "haste_pct", 1.5, [f"{class_key}_preview_{spec_key}"], 3))
    n.append(_stat_node(f"{pfx}_t0_c4", "Bloodlust", 4, 2, "lifesteal_pct", 1, [f"{class_key}_preview_{spec_key}"], 3))

    t1 = [f"{pfx}_t0_c1", t0]
    n.append(_spec_passive_node(f"{pfx}_t1_c2", sp.passive_name, 2, 3, passive_key, t1, 3))
    n.append(_proc_node(f"{pfx}_t1_c0", "Opportunist", 0, 3, "on_crit", t1, 3))
    n.append(_proc_node(f"{pfx}_t1_c4", "Executioner", 4, 3, "on_low_hp", t1, 2))

    t2 = [f"{pfx}_t1_c2"]
    n.append(_stat_node(f"{pfx}_t2_c1", "Overpower", 1, 4, pri, 4, t2, 3))
    n.append(_stat_node(f"{pfx}_t2_c3", "Relentless", 3, 4, "haste_pct", 2, t2, 3))
    n.append(_utility_node(f"{pfx}_t2_c0", "Treasure Sense", 0, 4, "gold_find", t2, 2))
    n.append(_utility_node(f"{pfx}_t2_c4", "Forge Student", 4, 4, "craft_xp", t2, 2))

    t3 = [f"{pfx}_t2_c1", f"{pfx}_t2_c3"]
    n.append(_proc_node(f"{pfx}_t3_c2", "Flurry", 2, 5, "on_hit", t3, 3))
    n.append(_stat_node(f"{pfx}_t3_c0", "Deadly Focus", 0, 5, "crit_pct", 2, t3, 2))

    n.append(
        _capstone_node(
            f"{pfx}_capstone",
            f"{sp.name} Mastery",
            2,
            6,
            [f"{pfx}_t3_c2", f"{pfx}_t1_c2"],
            [{"stat": pri, "flat": 10}, {"stat": "crit_pct", "flat": 3}],
        )
    )
    return n


def build_spec_tree(spec_key: str) -> Dict[str, Any]:
    sp = SPECIALIZATIONS[spec_key]
    class_key = sp.parent_class
    role = sp.role
    nodes = _role_templates(role, spec_key, class_key)
    return {
        "spec_key": spec_key,
        "class_key": class_key,
        "role": role,
        "passive_name": sp.passive_name,
        "nodes": nodes,
    }


def generate_all() -> None:
    _FOUNDATION_DIR.mkdir(parents=True, exist_ok=True)
    _SPECS_DIR.mkdir(parents=True, exist_ok=True)
    for ck in CLASSES:
        path = _FOUNDATION_DIR / f"{ck}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(build_foundation(ck), f, indent=2)
    for sk in SPECIALIZATIONS:
        path = _SPECS_DIR / f"{sk}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(build_spec_tree(sk), f, indent=2)
    print(f"Generated {len(CLASSES)} foundation + {len(SPECIALIZATIONS)} spec trees.")


if __name__ == "__main__":
    generate_all()
