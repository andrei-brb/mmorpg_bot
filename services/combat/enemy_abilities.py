"""
╔══════════════════════════════════════════════════════════════════════════════╗
║        services/combat/enemy_abilities.py — Boss signature moves            ║
╚══════════════════════════════════════════════════════════════════════════════╝

Every boss in the game already declares a signature kit. `config/settings.py`
gives Magmadar ``("lava_breath", "molten_armor")``, Gorgoth ``("stone_skin",
"petrify")``, Warlord Rend'ka ``("war_cry", "charge", "enrage")`` — 33 bosses,
39 distinct ability keys. The AI at ``combat_engine.CombatEngine.enemy_turn``
reads that tuple and picks from it.

Only two of those 39 keys existed in ``ABILITIES``. The other 37 fell through
``ABILITIES.get(key, ABILITIES["auto_attack"])`` (combat_engine.py:431) and
silently resolved to a plain swing — same damage, same narration, same name in
the log. So every named boss in the game fought exactly like trash with a bigger
health bar, and had done since the templates were written.

This module is the missing half. It is pure data — no import of combat_engine,
so there is no cycle; ``combat_engine`` builds the ``Ability`` objects from it
at import time and merges them into ``ABILITIES``.

── Design rules (pinned by tests/test_enemy_abilities.py) ────────────────────

1. **Nothing out-damages the existing ceiling.** ``mortal_strike`` is 1.9 and
   has been the hardest hit in the game for as long as bosses have existed.
   Nothing here exceeds it. Signature moves land in 1.3–1.7; AoE sits lower
   because it hits every party member.

2. **Cooldowns are the balance valve, not damage.** Before this, a boss rolled
   its "special" at 35% every single turn and nothing ever went on cooldown
   (the auto_attack fallback has ``cooldown=0``, so ``ability_cooldowns`` stayed
   empty forever). Real cooldowns of 3–6 turns mean a signature move is an
   event, not a coin flip. That is what keeps the difficulty change modest even
   though the moves themselves are now real.

3. **Elemental moves cut through armour, they do not ignore it.** The obvious
   implementation was ``ignores_armor=True``, which routes damage through the
   resistance branch at combat_engine.py:574 instead of the armour branch. That
   is wrong here, and measurably so: ``database/generate_items.py`` never sets
   ``s_resistance`` and nothing ever writes ``r_resistance``, so **every player
   has exactly 0 resistance** and that branch applies no mitigation at all. A
   level-30 character has ~68% armour reduction and 0% resistance reduction, so
   an armour-ignoring boss move would land roughly three times as hard as the
   same multiplier thrown physically — measured at +73% to +80% total boss
   damage on the fire bosses before this was changed.

   Instead, elemental moves use the ``armor_pen_pct`` hook the engine already
   has (combat_engine.py:568) at ``ELEMENTAL_ARMOR_PEN``. Plate still helps
   against dragon breath, just less than it helps against an axe — which is the
   distinction we wanted, at a magnitude the gear can actually answer. If
   resistance ever becomes a stat items grant, it can layer on top.

4. **Damage-over-time scales off the attacker.** ``Ability.effect_val`` is a
   flat integer (mortal_strike's bleed is 9), which is fine for a level-5 fight
   and meaningless against a level-60 boss. Enemy DoTs declare ``dot_scale``
   instead — a fraction of the attacker's attack power — so a boss's poison
   stays proportionate at every level.

5. **No move invents a mechanic the engine does not have.** Two keys wanted
   something real that does not exist: ``summon`` and ``beast_call`` should
   spawn adds, and the engine's ``session.enemies`` is fixed once a fight
   starts. Rather than fake it, they resolve as the swarm arriving — an AoE hit
   plus the boss growing stronger — and say so below. ``reflect`` is the same
   story: a true damage-reflect needs a hook in the damage path, so it is an
   absorb barrier and is named for what it does.
"""

from typing import Any, Dict

# Fraction of the caster's attack power used per damage-over-time tick.
#
# These look tiny next to the damage multipliers, and they have to be: a tick
# applied in `tick_turn` bypasses armour, dodge, crit and shields entirely,
# while a normal hit loses ~68% to armour at level 30. Measured against the
# bosses' own auto-attacks, a tick at 0.05 of attack power was worth about
# eight auto-attacks over its duration. Calibrated so a full DoT is worth
# roughly one mitigated swing — real pressure, never the main event.
_DOT_LIGHT = 0.008
_DOT_HEAVY = 0.014

#: The hardest single hit any enemy may land, as a damage multiplier.
#: Equal to ``mortal_strike`` — the pre-existing ceiling. Pinned by test.
MAX_ENEMY_DMG_MULT = 1.9

#: The hardest AoE hit. Lower than single-target because in a party dungeon it
#: lands on everyone at once.
MAX_ENEMY_AOE_MULT = 1.2

#: How much of the target's armour an ``elemental`` move cuts through. Applied
#: via the engine's existing ``armor_pen_pct`` path — see design rule 3 above
#: for why this is not ``ignores_armor``.
ELEMENTAL_ARMOR_PEN = 0.40


def _spec(
    name: str,
    emoji: str,
    desc: str,
    *,
    cooldown: int,
    dmg: float = 0.0,
    aoe: bool = False,
    elemental: bool = False,
    applies: str | None = None,
    val: int = 0,
    dur: int = 0,
    dot_scale: float = 0.0,
    tell: str = "",
) -> Dict[str, Any]:
    """One boss move.

    ``tell`` is the wind-up line the player sees the turn *before* it lands. It
    is written in present tense and describes the enemy's body, not the damage
    number — the player should be reading the boss, not a spreadsheet.
    """
    return {
        "name": name,
        "emoji": emoji,
        "desc": desc,
        "cooldown": cooldown,
        "dmg": dmg,
        "aoe": aoe,
        "elemental": elemental,
        "applies": applies,
        "val": val,
        "dur": dur,
        "dot_scale": dot_scale,
        "tell": tell,
    }


ENEMY_ABILITY_SPECS: Dict[str, Dict[str, Any]] = {

    # ── Heavy single-target ───────────────────────────────────────────────────
    # The bread and butter of a boss turn: one big telegraphed hit. These are
    # what Brace exists to answer.

    "charge": _spec(
        "Charge", "🐗", "Barrels into you, staggering you for a turn.",
        cooldown=4, dmg=1.5, applies="stun", dur=1,
        tell="digs in its heels, about to charge",
    ),
    "crush": _spec(
        "Crush", "🪨", "Brings its full weight down in a single blow.",
        cooldown=4, dmg=1.7,
        tell="raises both fists overhead",
    ),
    "ice_slam": _spec(
        "Ice Slam", "🧊", "A frozen blow that leaves you sluggish.",
        cooldown=3, dmg=1.5, applies="slow", val=30, dur=2,
        tell="hefts a slab of ice",
    ),
    "dive": _spec(
        "Dive", "🦅", "Drops out of the sky talons-first.",
        cooldown=3, dmg=1.6,
        tell="climbs, circling above you",
    ),
    "boarding": _spec(
        "Boarding Strike", "🪝", "A hooked blade that leaves you bleeding.",
        cooldown=3, dmg=1.4, applies="bleed", dur=3, dot_scale=_DOT_LIGHT,
        tell="swings a boarding hook loose",
    ),
    # ── Elemental single-target ───────────────────────────────────────────────
    # Skip armour, answered by resistance.

    "cannon_blast": _spec(
        "Cannon Blast", "💣", "A point-blank shot that ignores armour.",
        cooldown=4, dmg=1.6, elemental=True,
        tell="swings a deck gun around to bear",
    ),
    "lightning_strike": _spec(
        "Lightning Strike", "⚡", "Calls down a bolt that armour cannot stop.",
        cooldown=3, dmg=1.4, elemental=True,
        tell="draws the storm down toward you",
    ),
    "frequency_lance": _spec(
        "Frequency Lance", "📡", "A focused beam that cuts straight through plate.",
        cooldown=3, dmg=1.6, elemental=True,
        tell="spins up a resonant hum",
    ),
    "drill_pulse": _spec(
        "Drill Pulse", "🛠️", "A boring charge that leaves you exposed.",
        cooldown=4, dmg=1.5, elemental=True, applies="vulnerability", val=20, dur=2,
        tell="anchors itself and begins to bore",
    ),
    "haunt": _spec(
        "Haunt", "👻", "A spirit latches on and leaves you easier to wound.",
        cooldown=4, dmg=0.7, elemental=True, applies="vulnerability", val=25, dur=2,
        tell="reaches toward you with something that is not a hand",
    ),

    # ── Sweeping attacks ──────────────────────────────────────────────────────
    # Lower multipliers: in a party dungeon these land on everyone.

    "cleave": _spec(
        "Cleave", "🪓", "A wide swing that catches everyone in front of it.",
        cooldown=3, dmg=0.9, aoe=True,
        tell="winds up a wide swing",
    ),
    "stomp": _spec(
        "Stomp", "🦶", "Slams the ground hard enough to knock you off your feet.",
        cooldown=5, dmg=0.85, aoe=True, applies="stun", dur=1,
        tell="lifts one foot high",
    ),
    "earthquake": _spec(
        "Earthquake", "🌎", "The ground bucks and splits underfoot.",
        cooldown=5, dmg=1.05, aoe=True, applies="slow", val=30, dur=2,
        tell="drives its hands into the earth",
    ),
    "shatter_wave": _spec(
        "Shatter Wave", "💠", "A ring of flying glass that leaves everyone cut open.",
        cooldown=4, dmg=0.95, aoe=True, applies="vulnerability", val=20, dur=2,
        tell="hairline cracks race across its surface",
    ),
    "imperial_decree": _spec(
        "Imperial Decree", "👑", "A word of command that buckles the knees.",
        cooldown=5, dmg=1.0, aoe=True, applies="vulnerability", val=25, dur=2,
        tell="draws breath to speak",
    ),
    "madness_wave": _spec(
        "Madness Wave", "🌀", "A pulse of raw insanity that fogs the mind.",
        cooldown=4, dmg=0.9, aoe=True, elemental=True, applies="slow", val=35, dur=2,
        tell="its eyes roll back",
    ),
    "spectral_broadside": _spec(
        "Spectral Broadside", "🚢", "A full ghostly volley tears through the room.",
        cooldown=4, dmg=1.0, aoe=True, elemental=True,
        tell="a ghostly hull runs out its guns",
    ),

    # ── Elemental sweeps ──────────────────────────────────────────────────────

    "lava_breath": _spec(
        "Lava Breath", "🌋", "A cone of molten rock that keeps burning.",
        cooldown=4, dmg=1.1, aoe=True, elemental=True,
        applies="burn", dur=3, dot_scale=_DOT_HEAVY,
        tell="its throat glows red",
    ),
    "flame_nova": _spec(
        "Flame Nova", "🔥", "Erupts outward in a ring of fire.",
        cooldown=4, dmg=1.0, aoe=True, elemental=True,
        applies="burn", dur=3, dot_scale=_DOT_LIGHT,
        tell="heat begins to shimmer around it",
    ),
    "inferno": _spec(
        "Inferno", "☄️", "The whole room catches. Its heaviest strike.",
        cooldown=6, dmg=1.2, aoe=True, elemental=True,
        applies="burn", dur=3, dot_scale=_DOT_HEAVY,
        tell="the air itself starts to catch",
    ),
    "shadowflame": _spec(
        "Shadowflame", "🟣", "Fire that burns without light.",
        cooldown=4, dmg=1.05, aoe=True, elemental=True,
        applies="burn", dur=3, dot_scale=_DOT_LIGHT,
        tell="a black flame gutters along its jaw",
    ),
    "blizzard": _spec(
        "Blizzard", "❄️", "A killing wind that slows everything it touches.",
        cooldown=4, dmg=0.9, aoe=True, elemental=True, applies="slow", val=35, dur=2,
        tell="frost begins to crust the ground",
    ),

    # ── Reinforcements ────────────────────────────────────────────────────────
    # These want to spawn adds. `CombatSession.enemies` is fixed once a fight
    # starts, and faking a second health bar the UI cannot show would be worse
    # than not having it — so the swarm arrives as a hit and leaves the boss
    # emboldened. Named for what actually happens.

    "summon": _spec(
        # Not a self-buff: an ability may either damage its targets or buff its
        # caster, never both — `applies` lands on whoever the ability targets,
        # so pairing an AoE hit with `power_up` would hand the buff to the
        # players. The adds tie you down instead, which is the same fiction.
        "Summon Reinforcements", "📯", "Calls in help — they swarm and pin you down.",
        cooldown=5, dmg=0.8, aoe=True, applies="slow", val=30, dur=2,
        tell="throws its head back and calls out",
    ),
    "beast_call": _spec(
        "Beast Call", "🐺", "The pack answers and swarms you.",
        cooldown=4, dmg=0.95, aoe=True, applies="bleed", dur=3, dot_scale=_DOT_LIGHT,
        tell="lets out a long, answering howl",
    ),

    # ── Self-buffs ────────────────────────────────────────────────────────────
    # A turn spent not hitting you. Punish it — that is the read.

    "enrage": _spec(
        "Enrage", "😡", "Fury takes over; every blow lands harder.",
        cooldown=5, applies="power_up", val=30, dur=3,
        tell="starts to shake with rage",
    ),
    "frenzy": _spec(
        "Frenzy", "🌪️", "Whips itself into a killing frenzy.",
        cooldown=4, applies="power_up", val=25, dur=2,
        tell="its movements turn frantic",
    ),
    "blood_frenzy": _spec(
        "Blood Frenzy", "🩸", "The smell of blood drives it wild.",
        cooldown=5, applies="power_up", val=35, dur=3,
        tell="tastes the air and finds blood",
    ),
    "war_cry": _spec(
        "War Cry", "📣", "A roar that steadies its own line.",
        cooldown=5, applies="power_up", val=25, dur=3,
        tell="raises its weapon and bellows",
    ),

    # ── Defensive buffs ───────────────────────────────────────────────────────
    # Absorb barriers. Also a turn not spent hitting you — but this one is worth
    # burning your biggest hit into, because the barrier only soaks so much.

    "molten_armor": _spec(
        "Molten Armor", "🔥", "Sheathes itself in molten rock that soaks damage.",
        cooldown=5, applies="shield", val=0, dur=3,
        tell="molten rock begins to crust over its hide",
    ),
    "stone_skin": _spec(
        "Stone Skin", "🗿", "Its hide turns to stone.",
        cooldown=5, applies="shield", val=0, dur=3,
        tell="its skin darkens and hardens",
    ),
    "obsidian_aegis": _spec(
        "Obsidian Aegis", "🛡️", "A shell of black glass, harder than anything else it has.",
        cooldown=6, applies="shield", val=0, dur=3,
        tell="plates of black glass lock into place",
    ),
    "reflect": _spec(
        # A true damage-reflect needs a hook in the damage path that does not
        # exist. This is a barrier, and is named for what it does.
        "Mirror Ward", "🪞", "A mirrored ward that swallows incoming damage.",
        cooldown=5, applies="shield", val=0, dur=3,
        tell="a mirrored sheen crawls across it",
    ),

    # ── Control and damage-over-time ──────────────────────────────────────────
    # Low damage, high disruption. Cheap in HP, expensive in tempo.

    "freeze": _spec(
        "Freeze", "🥶", "Locks you in place for a turn.",
        cooldown=5, dmg=0.4, elemental=True, applies="stun", dur=1,
        tell="the air around you goes still and cold",
    ),
    "petrify": _spec(
        "Petrify", "🗿", "Its gaze turns your limbs to stone.",
        cooldown=5, dmg=0.3, elemental=True, applies="stun", dur=1,
        tell="turns its gaze directly on you",
    ),
    "web": _spec(
        "Web", "🕸️", "Sticky silk fouls your footing.",
        cooldown=3, dmg=0.3, applies="slow", val=40, dur=2,
        tell="rears back, spinnerets working",
    ),
    "stone_grasp": _spec(
        "Stone Grasp", "✋", "Stone hands close around your legs.",
        cooldown=3, dmg=0.5, applies="slow", val=35, dur=2,
        tell="the floor around your feet begins to move",
    ),
    "poison": _spec(
        "Poison", "☠️", "Venom that works while you fight.",
        cooldown=3, dmg=0.5, applies="poison", dur=3, dot_scale=_DOT_HEAVY,
        tell="venom beads along its fangs",
    ),
}

#: Elemental moves and how much armour they cut through. Consumed by
#: ``CombatEngine.use_ability`` through the existing armour-penetration path.
ELEMENTAL_KEYS: Dict[str, float] = {
    k: ELEMENTAL_ARMOR_PEN for k, v in ENEMY_ABILITY_SPECS.items() if v["elemental"]
}

#: Absorb barriers scale with the caster's own health so they stay meaningful at
#: every level, in the same spirit as ``dot_scale``. Value is a fraction of the
#: caster's max HP.
SHIELD_SCALE: Dict[str, float] = {
    "molten_armor": 0.06,
    "stone_skin": 0.08,
    "obsidian_aegis": 0.10,
    "reflect": 0.07,
}

#: Keys whose damage-over-time should scale off the caster rather than use the
#: flat ``effect_val``. Consumed by ``CombatEngine.use_ability``.
DOT_SCALE_BY_KEY: Dict[str, float] = {
    k: v["dot_scale"] for k, v in ENEMY_ABILITY_SPECS.items() if v["dot_scale"]
}

#: Wind-up lines, keyed by ability. Used to telegraph intent; see
#: ``CombatEngine.plan_enemy_turn``.
TELLS: Dict[str, str] = {k: v["tell"] for k, v in ENEMY_ABILITY_SPECS.items() if v["tell"]}

#: Tells for the boss moves that already existed before this module.
TELLS.setdefault("mortal_strike", "sets its feet for a killing blow")
TELLS.setdefault("whirlwind", "begins to spin, blade extended")
TELLS.setdefault("frost_nova", "frost spiders out from where it stands")
TELLS.setdefault("backstab", "slips out of your line of sight")
TELLS.setdefault("auto_attack", "closes in")


# ═══════════════════════════════════════════════════════════════════════════════
#  INTENT — what the player sees before it lands
# ═══════════════════════════════════════════════════════════════════════════════

#: Severity buckets. The player is told *how bad*, never the exact number: the
#: real figure depends on a damage roll, crit, armour, resistance and any
#: vulnerability, so a printed number would be a lie more often than not.
#: The bucket is honest and it is enough to decide on.
KIND_HEAVY = "heavy"      # one big hit — brace, heal, or stun it
KIND_SWEEP = "sweep"      # hits the whole party
KIND_STRIKE = "strike"    # ordinary damage
KIND_CONTROL = "control"  # stun / slow / vulnerability
KIND_EMPOWER = "empower"  # the enemy strengthens itself
KIND_GUARD = "guard"      # the enemy shields itself


def classify_intent(ability: Any) -> Dict[str, Any]:
    """Bucket an ability into something a player can read at a glance.

    Takes any object with the ``Ability`` field names — kept duck-typed so this
    module stays free of a combat_engine import (and therefore free of a cycle).
    """
    dmg = float(getattr(ability, "dmg_mult", 0.0) or 0.0)
    aoe = bool(getattr(ability, "is_aoe", False))
    applies = getattr(ability, "applies", None)
    applies_val = getattr(applies, "value", applies)

    if applies_val == "shield":
        kind = KIND_GUARD
    elif applies_val == "power_up" and dmg <= 0:
        kind = KIND_EMPOWER
    elif aoe and dmg > 0:
        kind = KIND_SWEEP
    elif dmg >= 1.4:
        kind = KIND_HEAVY
    elif applies_val in ("stun", "slow", "vulnerability", "silenced") and dmg < 1.4:
        kind = KIND_CONTROL
    elif dmg > 0:
        kind = KIND_STRIKE
    else:
        kind = KIND_CONTROL

    # Three levels only. More would imply a precision we do not have.
    if kind in (KIND_SWEEP,):
        severity = 3 if dmg >= 1.0 else 2
    elif kind == KIND_HEAVY:
        severity = 3
    elif kind in (KIND_EMPOWER, KIND_GUARD, KIND_CONTROL):
        severity = 2
    else:
        severity = 1

    return {"kind": kind, "severity": severity}
