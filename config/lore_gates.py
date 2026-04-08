"""
Lore boss gates — Obsidian Silence / story progression.

Only enforced when CombatSession.apply_lore_gates is True (Discord /fight & explore).
Activity combat tab and dungeons set apply_lore_gates=False so gear/leveling loops are unaffected.

Add entries as you implement enemies and key items in the DB.
"""

from typing import Any, Dict, List, Optional, TypedDict


class LoreBossGateDict(TypedDict, total=False):
    """Gate rule for one enemy_key."""

    required_flags: List[str]  # deed flags on character_deed_flags
    required_items: List[str]  # item_templates.id — ALL must be in inventory
    hint: str  # shown to player when immune


# Enemy key must match config.settings ENEMIES / zone boss keys.
LORE_BOSS_GATES: Dict[str, LoreBossGateDict] = {
    "gorgoth_petrified": {
        "required_flags": ["has_shatter_tone_fork"],
        "required_items": [],
        "hint": "Complete **The Shatter-Tone** with the **Mage Apprentice** in Elwynn—then the fork can fracture this stillness.",
    },
    "kaelen_tor_stabilizer": {
        "required_flags": ["seismic_trigger_complete", "marcus_recommendation"],
        "required_items": [],
        "hint": "Earn **Marcus's word** in Elwynn, then arm the **Seismic Trigger** with **Steelhammer** before you punch the drill.",
    },
    "lord_incendius": {
        "required_flags": ["gorgoth_defeated"],
        "required_items": [],
        "hint": "Prove the Graying bleeds: defeat **Gorgoth the Petrified** in Elwynn first.",
    },
    "emperor_dagran_thaurissan": {
        "required_flags": ["cipher_translated"],
        "required_items": [],
        "hint": "Translate the coastal cipher with the **Archaeologist** in Stranglethorn before the Throne will answer.",
    },
    "vaelkor_architect": {
        "required_flags": ["trisect_key_forged"],
        "required_items": [],
        "hint": "Forge the **Trisect Key** with **Eldric** in Blackrock—three proofs of motion, one honest approach.",
    },
}


def get_gate(enemy_key: str) -> Optional[LoreBossGateDict]:
    return LORE_BOSS_GATES.get(enemy_key)
