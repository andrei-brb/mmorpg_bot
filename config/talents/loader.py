"""
Load talent definitions from JSON under config/talents/.
Trees are generated via scripts/generate_talent_trees.py if missing.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

from config.settings import CLASSES, SPECIALIZATIONS

_TALENTS_DIR = Path(__file__).resolve().parent
_FOUNDATION_DIR = _TALENTS_DIR / "foundation"
_SPECS_DIR = _TALENTS_DIR / "specs"


def talent_points_for_level(level: int) -> int:
    """Grant +1 talent point on even character levels (2, 4, …, 60)."""
    lv = max(0, int(level))
    return 1 if lv >= 2 and lv % 2 == 0 else 0


def total_talent_points_for_level(level: int) -> int:
    """Cumulative spendable points earned by reaching `level`."""
    return sum(talent_points_for_level(lv) for lv in range(2, int(level) + 1))


def list_class_specs(class_key: str) -> List[str]:
    cls = CLASSES.get(class_key)
    if not cls:
        return []
    return list(cls.specializations)


@lru_cache(maxsize=16)
def get_class_foundation(class_key: str) -> Dict[str, Any]:
    path = _FOUNDATION_DIR / f"{class_key}.json"
    if not path.is_file():
        _ensure_trees_generated()
    if path.is_file():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {"class_key": class_key, "nodes": []}


@lru_cache(maxsize=32)
def get_spec_tree(spec_key: str) -> Dict[str, Any]:
    path = _SPECS_DIR / f"{spec_key}.json"
    if not path.is_file():
        _ensure_trees_generated()
    if path.is_file():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {"spec_key": spec_key, "nodes": []}


def get_node_def(node_id: str, class_key: str, spec_key: Optional[str]) -> Optional[Dict[str, Any]]:
    """Resolve a node id from foundation or spec tree."""
    found = _find_in_tree(get_class_foundation(class_key), node_id)
    if found:
        return found
    if spec_key:
        found = _find_in_tree(get_spec_tree(spec_key), node_id)
        if found:
            return found
    for sk in list_class_specs(class_key):
        if sk == spec_key:
            continue
        found = _find_in_tree(get_spec_tree(sk), node_id)
        if found:
            return found
    return None


def _find_in_tree(tree: Dict[str, Any], node_id: str) -> Optional[Dict[str, Any]]:
    for n in tree.get("nodes") or []:
        if str(n.get("id")) == node_id:
            return n
    return None


def all_nodes_for_character(class_key: str, spec_key: Optional[str]) -> List[Dict[str, Any]]:
    nodes: List[Dict[str, Any]] = []
    nodes.extend(list(get_class_foundation(class_key).get("nodes") or []))
    if spec_key:
        nodes.extend(list(get_spec_tree(spec_key).get("nodes") or []))
    for sk in list_class_specs(class_key):
        if sk != spec_key:
            nodes.extend(list(get_spec_tree(sk).get("nodes") or []))
    return nodes


def _ensure_trees_generated() -> None:
    try:
        from config.talents.generate_trees import generate_all

        generate_all()
    except Exception:
        pass


def invalidate_cache() -> None:
    get_class_foundation.cache_clear()
    get_spec_tree.cache_clear()
