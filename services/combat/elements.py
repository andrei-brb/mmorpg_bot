"""
╔══════════════════════════════════════════════════════════════════════════════╗
║          services/combat/elements.py — Elemental matchups                   ║
╚══════════════════════════════════════════════════════════════════════════════╝

Why this exists: pressing your highest-damage button was always the right answer.
Every ability differed only in a number, so "which spell do I cast" had one
correct answer for the whole game and combat never asked a second question.

Matchups give the encounter a say. A frost giant resists frost and burns to
fire; a fire elemental is the reverse. The *same* character makes different
choices in different fights, using the kit they already have — no new content,
no new buttons.

── Scope, deliberately ───────────────────────────────────────────────────────

Matchups apply to **the player's offence only**. Enemy damage is untouched.

That is a real choice, not an omission. Bosses just gained working signature
moves (see enemy_abilities.py) and got measurably harder; layering an elemental
multiplier onto *incoming* damage as well would stack two difficulty changes in
one release and neither could be judged on its own. Player-side also keeps the
mechanic where the decision is — you choose which ability to press; you do not
choose what the boss throws.

── Calibration ───────────────────────────────────────────────────────────────

Strong is +20%, weak is -15%. Modest on purpose: a player who always picks the
right element gains about a fifth more damage, which roughly offsets the boss
damage increase that shipped alongside it. Big enough to be worth reading, small
enough that a character without the right element in their kit is not locked out
of a fight.

Anything physical is neutral both ways — a sword is a sword. That matters more
than it sounds: warriors and rogues are largely physical, so this system must
never make them second-class. They trade the upside for never having a bad
matchup.

── A known content gap ───────────────────────────────────────────────────────

Measured across the current roster, how much each element's bonus is actually
worth:

    fire    4 abilities -> strong vs nature (32 enemies)
    frost   4 abilities -> strong vs shadow (16 enemies)
    nature  4 abilities -> strong vs frost  (10 enemies)
    holy   12 abilities -> strong vs fire   (16 enemies)
    shadow  4 abilities -> strong vs holy   ( 1 enemy)

Shadow's bonus is close to worthless because the game contains exactly one holy
enemy (goldshire_guard). That is a gap in the enemy roster, not in the ring —
rotating the cycle only moves the dead spot onto a different element. Fixing it
means adding holy-aligned enemies (consecrated guardians, zealots, an order of
paladins), which is content work and is deliberately not done here.
"""

from typing import Any, Dict, Optional

FIRE = "fire"
FROST = "frost"
NATURE = "nature"
SHADOW = "shadow"
HOLY = "holy"
PHYSICAL = "physical"

#: Strong is a bonus, weak is a penalty. See the calibration note above.
STRONG_MULT = 1.20
WEAK_MULT = 0.85

#: element -> the element it is strong against.
#:
#: One five-element cycle, no special cases. Every element beats exactly one and
#: loses to exactly one, so no choice is globally correct and none is a free
#: bonus.
#:
#: The first draft had holy and shadow outside the ring as *mutual* opposites,
#: which a test caught: mutual means each is strong against the other and
#: neither is ever penalised, i.e. a pure buff to both. A cycle cannot have that
#: hole.
#:
#:   fire   burns the wilds
#:   nature cracks the ice
#:   frost  stills the restless dead
#:   shadow smothers the light
#:   holy   quenches infernal flame
BEATS: Dict[str, str] = {
    FIRE: NATURE,
    NATURE: FROST,
    FROST: SHADOW,
    SHADOW: HOLY,
    HOLY: FIRE,
}

#: Reverse lookup: element -> what beats it. This is what a player is shown.
BEATEN_BY: Dict[str, str] = {v: k for k, v in BEATS.items()}

ELEMENT_LABEL: Dict[str, str] = {
    FIRE: "Fire",
    FROST: "Frost",
    NATURE: "Nature",
    SHADOW: "Shadow",
    HOLY: "Holy",
    PHYSICAL: "Physical",
}

ELEMENT_EMOJI: Dict[str, str] = {
    FIRE: "🔥",
    FROST: "❄️",
    NATURE: "🌿",
    SHADOW: "🌑",
    HOLY: "✨",
    PHYSICAL: "⚔️",
}

# ── Player abilities ──────────────────────────────────────────────────────────
# Only abilities whose element is unambiguous from what they already are. Every
# ability not listed is physical and therefore always neutral — an omission here
# is safe, which is why the map is explicit rather than inferred from the name.

ABILITY_ELEMENT: Dict[str, str] = {
    # Mage — fire
    "fireball": FIRE,
    "pyroblast": FIRE,
    "combustion": FIRE,
    "dragon_breath": FIRE,
    # Mage — frost
    "frost_bolt": FROST,
    "frost_nova": FROST,
    "ice_lance": FROST,
    "frozen_orb": FROST,
    # Priest / Paladin — holy
    "smite": HOLY,
    "holy_light": HOLY,
    "holy_shock": HOLY,
    "judgment": HOLY,
    "divine_storm": HOLY,
    "hammer_of_wrath": HOLY,
    "crusader_strike": HOLY,
    "heal": HOLY,
    "circle_of_healing": HOLY,
    "prayer_of_mending": HOLY,
    "beacon_of_light": HOLY,
    "lay_on_hands": HOLY,
    # Priest shadow / Rogue shadow
    "mind_blast": SHADOW,
    "vampiric_touch": SHADOW,
    "void_eruption": SHADOW,
    "shadowstrike": SHADOW,
    # Rogue poisons / Hunter beasts — nature
    "envenom": NATURE,
    "kill_command": NATURE,
    "dire_beast": NATURE,
    "bestial_wrath": NATURE,
}

# ── Enemy signature moves ─────────────────────────────────────────────────────
# An enemy's element is read from its own kit first (see enemy_element), so this
# map is what makes that work — and it means adding a fire move to a boss makes
# that boss fire, with no second place to update.

ENEMY_ABILITY_ELEMENT: Dict[str, str] = {
    "lava_breath": FIRE,
    "flame_nova": FIRE,
    "inferno": FIRE,
    "molten_armor": FIRE,
    "shadowflame": SHADOW,
    "blizzard": FROST,
    "freeze": FROST,
    "ice_slam": FROST,
    "haunt": SHADOW,
    "madness_wave": SHADOW,
    "spectral_broadside": SHADOW,
    "poison": NATURE,
    "web": NATURE,
    "beast_call": NATURE,
    "petrify": NATURE,
    "stone_grasp": NATURE,
    "stone_skin": NATURE,
    "lightning_strike": NATURE,
    "frost_nova": FROST,
}

# ── Enemies without a kit ─────────────────────────────────────────────────────
# 65 of 98 enemies declare no abilities, so their element comes from what they
# plainly are. Ordered: the first match wins, so put the specific before the
# general ("frost_giant" before "giant").

_KEYWORD_ELEMENT = [
    # Fire
    ("lava", FIRE), ("magma", FIRE), ("molten", FIRE), ("flame", FIRE),
    ("fire", FIRE), ("ember", FIRE), ("incendius", FIRE), ("pyre", FIRE),
    ("ash_", FIRE), ("firelord", FIRE), ("blackrock", FIRE),
    # Frost
    ("frost", FROST), ("ice_", FROST), ("winter", FROST), ("snow", FROST),
    ("frozen", FROST), ("frostmane", FROST),
    # Shadow / undead
    ("shadow", SHADOW), ("dark_", SHADOW), ("ghoul", SHADOW), ("ghost", SHADOW),
    ("wraith", SHADOW), ("skeletal", SHADOW), ("haunted", SHADOW),
    ("cultist", SHADOW), ("cult_", SHADOW), ("grave", SHADOW),
    ("forsaken", SHADOW), ("void", SHADOW), ("nightmare", SHADOW),
    ("warlock", SHADOW), ("morlan", SHADOW), ("duskwood", SHADOW),
    # Nature — beasts, plants, the living world
    ("spider", NATURE), ("widow", NATURE), ("wolf", NATURE), ("worg", NATURE),
    ("bear", NATURE), ("bat", NATURE), ("boar", NATURE), ("raptor", NATURE),
    ("lizard", NATURE), ("crocodile", NATURE), ("panther", NATURE),
    ("tiger", NATURE), ("leopard", NATURE), ("ape", NATURE), ("stag", NATURE),
    ("vulture", NATURE), ("scorpion", NATURE), ("chimera", NATURE),
    ("basilisk", NATURE), ("hawk", NATURE), ("zhevra", NATURE),
    ("plainstrider", NATURE), ("quillboar", NATURE), ("murloc", NATURE),
    ("stalker", NATURE), ("prowler", NATURE), ("drake", NATURE),
    ("dragon", FIRE),
    # Holy
    ("goldshire", HOLY), ("guard", HOLY),
]


def ability_element(key: str) -> str:
    """The element of a player ability. Unlisted means physical."""
    return ABILITY_ELEMENT.get(key, PHYSICAL)


def enemy_element(enemy_key: Optional[str]) -> str:
    """The element of an enemy.

    Its own signature kit wins — a boss that breathes lava is fire, and stays
    fire if someone renames it. Only enemies with no kit fall back to what their
    key says they are.
    """
    if not enemy_key:
        return PHYSICAL
    try:
        from config.settings import ENEMIES

        tmpl = ENEMIES.get(enemy_key)
    except Exception:
        tmpl = None

    if tmpl is not None:
        votes: Dict[str, int] = {}
        for ab in (getattr(tmpl, "abilities", None) or ()):
            el = ENEMY_ABILITY_ELEMENT.get(ab)
            if el:
                votes[el] = votes.get(el, 0) + 1
        if votes:
            # Most-represented element in the kit; ties break alphabetically so
            # the same boss always reads the same way.
            return sorted(votes.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]

    k = enemy_key.lower()
    for needle, el in _KEYWORD_ELEMENT:
        if needle in k:
            return el
    return PHYSICAL


def matchup(attack_element: str, defender_element: str) -> float:
    """Damage multiplier for attacking `defender_element` with `attack_element`."""
    if attack_element == PHYSICAL or defender_element == PHYSICAL:
        return 1.0
    if BEATS.get(attack_element) == defender_element:
        return STRONG_MULT
    if BEATS.get(defender_element) == attack_element:
        return WEAK_MULT
    return 1.0


def effectiveness(attack_element: str, defender_element: str) -> str:
    """`strong` | `weak` | `neutral` — what a skill button should show."""
    m = matchup(attack_element, defender_element)
    if m > 1.0:
        return "strong"
    if m < 1.0:
        return "weak"
    return "neutral"


def enemy_element_payload(enemy_key: Optional[str]) -> Dict[str, Any]:
    """The enemy's element and what beats it, for the combat panel.

    Physical enemies report no weakness rather than a made-up one — telling a
    player to bring fire against a bandit would be a lie.
    """
    el = enemy_element(enemy_key)
    weak_to = BEATEN_BY.get(el)
    return {
        "element": el,
        "element_label": ELEMENT_LABEL.get(el, el.title()),
        "element_emoji": ELEMENT_EMOJI.get(el, ""),
        "weak_to": weak_to,
        "weak_to_label": ELEMENT_LABEL.get(weak_to) if weak_to else None,
        "weak_to_emoji": ELEMENT_EMOJI.get(weak_to, "") if weak_to else None,
    }
