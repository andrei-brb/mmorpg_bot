"""
Combat hooks for talent spec-passive scaling and proc registry.
"""

from __future__ import annotations

import random
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from services.combat.combat_engine import StatusEffect

if TYPE_CHECKING:
    from services.combat.combat_engine import Combatant, CombatResult

SPEC_PASSIVE_POTENCY_PER_RANK = 0.12
MAX_PROC_CHANCE_PER_ID = 0.35


def spec_passive_mult(spec_passive_rank: int) -> float:
    """Scale spec passive bonuses by invested spec_passive talent ranks."""
    r = max(0, int(spec_passive_rank))
    return 1.0 + SPEC_PASSIVE_POTENCY_PER_RANK * r


def spec_passive_mult_for(combatant: Any) -> float:
    return spec_passive_mult(getattr(combatant, "talent_spec_passive_rank", 0) or 0)


def merge_proc_chances(procs: List[Dict[str, Any]]) -> Dict[str, float]:
    out: Dict[str, float] = {}
    for p in procs or []:
        pid = str(p.get("proc_id") or "").strip()
        if not pid:
            continue
        out[pid] = min(MAX_PROC_CHANCE_PER_ID, out.get(pid, 0.0) + float(p.get("chance") or 0))
    return out


def attach_talent_combat_fields(combatant: Any, effects: Optional[Dict[str, Any]]) -> None:
    effects = effects or {}
    combatant.talent_spec_passive_rank = int(effects.get("spec_passive_rank") or 0)
    combatant.talent_procs = merge_proc_chances(effects.get("procs") or [])


async def fetch_talent_effects(db, char_id, class_key: str, spec_key: Optional[str]) -> Dict[str, Any]:
    from services.talents.talent_service import TalentService

    return await TalentService(db).aggregate_effects(char_id, class_key, spec_key)


def _proc_chance(combatant: Any, proc_id: str) -> float:
    procs = getattr(combatant, "talent_procs", None) or {}
    return float(procs.get(proc_id) or 0)


def apply_talent_damage_procs(
    attacker: Any,
    target: Any,
    raw: int,
    *,
    is_crit: bool,
) -> int:
    """Modify outgoing damage from talent procs (attacker-owned)."""
    if raw <= 0:
        return raw
    if is_crit:
        ch = _proc_chance(attacker, "on_crit")
        if ch > 0 and random.random() < ch:
            raw = int(raw * 1.12)
    ch = _proc_chance(attacker, "on_hit")
    if ch > 0 and random.random() < ch:
        raw = int(raw * 1.08)
    if getattr(attacker, "hp_pct", 100) < 35:
        ch = _proc_chance(attacker, "on_low_hp")
        if ch > 0:
            raw = int(raw * (1 + ch))
    return raw


def apply_talent_damage_taken_procs(
    defender: Any,
    raw: int,
    result: Optional["CombatResult"] = None,
) -> int:
    """Modify incoming damage on the defender from talent procs."""
    if raw <= 0:
        return raw
    ch = _proc_chance(defender, "on_block")
    if ch > 0 and random.random() < ch:
        raw = int(raw * (1 - min(0.25, ch)))
        if result is not None:
            result.log += " 🛡️ Block proc"
    if getattr(defender, "hp_pct", 100) < 30:
        ch = _proc_chance(defender, "low_hp_save")
        if ch > 0 and random.random() < ch:
            shield_val = max(12, int(defender.max_hp * 0.08))
            defender.add_status(StatusEffect.SHIELD, shield_val, 2, "talent_save")
            if result is not None:
                result.log += f" 💫 Last Stand (+{shield_val} absorb)"
    return raw


def try_talent_on_hit_slow(attacker: Any, target: Any, result: Optional["CombatResult"] = None) -> None:
    ch = _proc_chance(attacker, "on_hit_slow")
    if ch <= 0 or random.random() >= ch:
        return
    target.add_status(StatusEffect.SLOW, 8, 1, attacker.name)
    if result is not None:
        result.effects_added.append("slow")
        result.log += " ❄️ Slowing strike"


def apply_talent_heal_procs(
    attacker: Any,
    heal_target: Any,
    actual_heal: int,
    result: Optional["CombatResult"] = None,
) -> None:
    if actual_heal <= 0:
        return
    ch = _proc_chance(attacker, "on_heal")
    if ch > 0 and random.random() < ch:
        bonus = max(4, int(actual_heal * 0.08))
        heal_target.add_status(StatusEffect.SHIELD, bonus, 1, "talent_heal")
        if result is not None:
            result.effects_added.append("talent_absorb")
            result.log += f" (+{bonus} absorb)"
    ch = _proc_chance(attacker, "on_heal_hot")
    if ch > 0 and random.random() < ch:
        hot = max(3, int(actual_heal * 0.05))
        heal_target.current_hp = min(heal_target.max_hp, heal_target.current_hp + hot)
        if result is not None:
            result.log += f" (+{hot} renew)"
