"""
╔══════════════════════════════════════════════════════════════════════════════╗
║       services/combat/consumables.py — Items you can use mid-fight          ║
╚══════════════════════════════════════════════════════════════════════════════╝

Before this, the only thing you could use in a fight was **one healing potion**,
found by a query hardcoded to ``effect_type = 'heal_hp'``
(activity_combat._has_healing_potion). Every other consumable the game sells is
a ten-minute out-of-combat stat buff, which is a shopping decision, not a combat
one — you drink it before you leave town and forget about it.

So "use an item" was a single button that did a single thing, and the answer to
"should I press it" was always "yes, when low". That is not a decision.

── What these are for ────────────────────────────────────────────────────────

Each combat consumable answers something the fight now actually creates, so the
choice of *which* to carry and *when* to spend it is a real one:

  ``combat_cure``     the damage-over-time bosses apply — lava_breath's burn,
                      poison, the bleed off a boarding strike. Curing early
                      wastes it; curing late means you already ate the ticks.
  ``combat_restore``  running dry. Bracing costs you a turn of damage, and a
                      caster who spent everything has nothing to punish a
                      boss's buff turn with.
  ``combat_shield``   a telegraphed heavy hit. Overlaps with Brace deliberately
                      — Brace is free but costs your turn, the stone costs an
                      item but not your turn.
  ``combat_damage``   burst that ignores the elemental matchup, so a physical
                      class has *something* to reach for in a fight where they
                      have no strong element (see elements.py).

── Magnitudes scale, they are not flat ──────────────────────────────────────

``item_templates.effect_value`` is a flat integer, which is how the healing
potion ended up as "80" — meaningful at level 5 and irrelevant at 60. For these
the stored value is a **percentage** and the real number is resolved here
against the character, so an item bought at level 10 is still worth carrying at
60.

``combat_damage`` is the exception and takes its number from the *user's* attack
power rather than a stored value, for the same reason.
"""

from typing import Any, Dict, List, Optional, Tuple

from services.combat.combat_engine import Combatant, StatusEffect

#: Effect types that resolve inside a fight. Anything else stays an
#: out-of-combat consumable and is rejected with a reason the player can act on.
COMBAT_EFFECTS = {
    "heal_hp",
    "combat_cure",
    "combat_restore",
    "combat_shield",
    "combat_damage",
}

#: Damage-over-time effects an antidote clears. Deliberately not SLOW or STUN —
#: a cure that also broke crowd control would replace three counters with one.
CURABLE = (StatusEffect.BURN, StatusEffect.BLEED, StatusEffect.POISON)

#: Alchemist's Fire damage, as a share of the thrower's attack power.
#:
#: Sized deliberately: this lands UNMITIGATED, and using an item does not end
#: your turn (matching the healing potion, which has always been a free action —
#: changing that would be a stealth nerf to how people already play). Free and
#: unmitigated is a dangerous combination, so the number is pinned to roughly
#: one good ability hit AFTER armour, not to the raw multiplier. A first pass at
#: 0.55 worked out to about six auto-attacks' worth, three times a fight, for
#: free.
THROWN_DAMAGE_AP_SHARE = 0.20

#: Its burn, per tick, also as a share of attack power. Matches the light DoT
#: band in enemy_abilities.py — ticks bypass armour, so they must stay small.
THROWN_BURN_AP_SHARE = 0.008
THROWN_BURN_TURNS = 3

#: How many items you may use in one fight. One was the old healing-potion
#: limit; three lets you actually combine them without turning a fight into an
#: inventory queue.
MAX_ITEMS_PER_FIGHT = 3


def is_combat_usable(effect_type: Optional[str]) -> bool:
    return bool(effect_type) and effect_type in COMBAT_EFFECTS


def apply_combat_consumable(
    effect_type: str,
    effect_value: int,
    item_name: str,
    user: Combatant,
    enemy: Optional[Combatant],
) -> Tuple[bool, str]:
    """Resolve one consumable against live combatants.

    Returns ``(changed_anything, log_line)``. A consumable that would do nothing
    reports ``False`` so the caller can refuse it *before* spending the item —
    burning an antidote while clean should not cost you the antidote.
    """
    ev = int(effect_value or 0)

    if effect_type == "heal_hp":
        # The stored value is flat and dates from level-5 content, so treat it
        # as a floor and scale the real heal off the character.
        heal = max(ev, int(user.max_hp * 0.25))
        healed = min(heal, user.max_hp - user.current_hp)
        if healed <= 0:
            return False, f"You are already at full health — **{item_name}** would do nothing."
        user.current_hp += healed
        return True, f"🧪 **{user.name}** drinks **{item_name}** — restored **{healed}** HP."

    if effect_type == "combat_cure":
        cleared = [s.effect.value for s in user.status_effects if s.effect in CURABLE]
        if not cleared:
            return False, f"Nothing to purge — **{item_name}** would do nothing."
        for eff in CURABLE:
            user.remove_status(eff)
        return True, f"🧯 **{item_name}** purges *{', '.join(cleared)}*."

    if effect_type == "combat_restore":
        if user.max_res <= 0:
            return False, f"You have no resource to restore — **{item_name}** would do nothing."
        gain = min(max(1, int(user.max_res * (ev or 40) / 100)), user.max_res - user.current_res)
        if gain <= 0:
            return False, f"Your {user.res_type} is already full — **{item_name}** would do nothing."
        user.current_res += gain
        return True, f"🔷 **{item_name}** restores **{gain}** {user.res_type}."

    if effect_type == "combat_shield":
        absorb = max(1, int(user.max_hp * (ev or 35) / 100))
        # Duration 1: it is for the hit you can see coming, not a standing buff.
        user.add_status(StatusEffect.SHIELD, absorb, 1, "warding_stone")
        return True, f"🪬 **{item_name}** wards you — absorbing up to **{absorb}** damage."

    if effect_type == "combat_damage":
        if enemy is None or enemy.is_dead:
            return False, f"Nothing to throw it at — **{item_name}** would do nothing."
        dmg = max(1, int(user.attack_power * THROWN_DAMAGE_AP_SHARE))
        enemy.current_hp = max(0, enemy.current_hp - dmg)
        if enemy.current_hp == 0:
            enemy.is_dead = True
        burn = max(1, int(user.attack_power * THROWN_BURN_AP_SHARE))
        enemy.add_status(StatusEffect.BURN, burn, THROWN_BURN_TURNS, "alchemists_fire")
        return True, (
            f"💥 **{item_name}** bursts on **{enemy.name}** for **{dmg}** damage and sets it burning."
        )

    return False, f"**{item_name}** cannot be used in combat."


async def usable_combat_items(db, char_id) -> List[Dict[str, Any]]:
    """Everything in the bag that does something in a fight, for the UI.

    The old flow could only ever show one healing potion because that was the
    only thing the query looked for.
    """
    rows = await db.fetch(
        """
        SELECT i.id, i.quantity, t.name, t.icon, t.effect_type, t.effect_value, t.description
        FROM inventory i
        JOIN item_templates t ON i.template_id = t.id
        WHERE i.character_id = $1
          AND i.quantity > 0
          AND t.item_type = 'consumable'
          AND t.effect_type = ANY($2::text[])
        ORDER BY t.effect_type, t.effect_value DESC
        """,
        char_id,
        sorted(COMBAT_EFFECTS),
    )
    return [
        {
            "id": str(r["id"]),
            "name": r["name"],
            "icon": r["icon"] or "🧪",
            "quantity": int(r["quantity"]),
            "effect_type": r["effect_type"],
            "description": r["description"] or "",
        }
        for r in rows
    ]
