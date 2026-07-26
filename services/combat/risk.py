"""
╔══════════════════════════════════════════════════════════════════════════════╗
║             services/combat/risk.py — Opt-in risk                           ║
╚══════════════════════════════════════════════════════════════════════════════╝

Difficulty in this game has only ever been chosen by *where you go*: an enemy is
as hard as its zone and its level, and once you outgear a zone every fight in it
is free. There has been no way to say "I am stronger than this content, make it
worth my time" short of walking into a zone that flatly kills you.

Oaths are that dial. You accept a handicap before the fight and the fight pays
more. Nothing is unlocked, nothing is spent — you simply choose to make it
harder, and the reward is proportional to what you gave up.

── What makes an oath good ───────────────────────────────────────────────────

Each one removes something the player *would otherwise use*, which is only
possible because the rest of this work gave them things to use:

  Blind     turns off the intent telegraph — you fight the way the game played
            before enemy intent existed.
  Bare      no consumables.
  Brittle   you take more damage.
  Patient   the boss opens already cornered, in its phase-3 signature rate.

They stack, and the bonus stacks multiplicatively, so taking three is worth
meaningfully more than taking one. There is no cap other than the four oaths
themselves, because the handicaps are real — a Blind, Bare, Brittle, Patient
fight is genuinely dangerous, and a player who clears one has earned the number.

── What an oath must never do ────────────────────────────────────────────────

Change the *loot table*. Rewards here scale XP and gold only. Letting a handicap
raise drop rarity would make oaths mandatory for anyone chasing an item rather
than optional, and "optional" is the whole idea. Pinned by a test.
"""

from typing import Any, Dict, List

#: id -> definition. `reward_mult` is what the oath pays; the rest are flags the
#: combat code reads.
OATHS: Dict[str, Dict[str, Any]] = {
    "blind": {
        "name": "Blind Oath",
        "emoji": "🙈",
        "description": "The enemy tells you nothing. No intent, no wind-up.",
        "reward_mult": 1.25,
        "hide_intent": True,
    },
    "bare": {
        "name": "Bare Oath",
        "emoji": "🚫",
        "description": "No potions, no consumables. Only what you can do yourself.",
        "reward_mult": 1.20,
        "no_items": True,
    },
    "brittle": {
        "name": "Brittle Oath",
        "emoji": "💔",
        "description": "You take 40% more damage.",
        "reward_mult": 1.45,
        "damage_taken_mult": 1.40,
    },
    "patient": {
        "name": "Patient Oath",
        "emoji": "⏳",
        "description": "The enemy starts cornered and fights that way from the first turn.",
        "reward_mult": 1.30,
        "start_enraged": True,
    },
}

#: Cap on the combined multiplier. Four oaths compound to about 2.7x; this only
#: exists so a future fifth oath cannot quietly turn into an economy exploit.
MAX_REWARD_MULT = 3.0


def normalize(raw: Any) -> List[str]:
    """Accept whatever the client sent and return known oath ids, deduplicated.

    Unknown ids are dropped rather than rejected: an older client sending a
    since-renamed oath should get an ordinary fight, not an error.
    """
    if not raw:
        return []
    if isinstance(raw, str):
        raw = [raw]
    if not isinstance(raw, (list, tuple, set)):
        return []
    seen: List[str] = []
    for item in raw:
        key = str(item).strip().lower()
        if key in OATHS and key not in seen:
            seen.append(key)
    return seen


def reward_multiplier(oaths: List[str]) -> float:
    """Multiplicative, so stacking is worth more than the sum of its parts."""
    mult = 1.0
    for key in oaths:
        mult *= float(OATHS[key]["reward_mult"])
    return min(mult, MAX_REWARD_MULT)


def _flag(oaths: List[str], name: str) -> bool:
    return any(OATHS[k].get(name) for k in oaths)


def hides_intent(oaths: List[str]) -> bool:
    return _flag(oaths, "hide_intent")


def forbids_items(oaths: List[str]) -> bool:
    return _flag(oaths, "no_items")


def starts_enraged(oaths: List[str]) -> bool:
    return _flag(oaths, "start_enraged")


def damage_taken_multiplier(oaths: List[str]) -> float:
    mult = 1.0
    for key in oaths:
        mult *= float(OATHS[key].get("damage_taken_mult", 1.0))
    return mult


def catalog() -> List[Dict[str, Any]]:
    """Every oath, for the pre-fight screen."""
    return [
        {
            "id": key,
            "name": o["name"],
            "emoji": o["emoji"],
            "description": o["description"],
            "reward_bonus_pct": int(round((float(o["reward_mult"]) - 1.0) * 100)),
        }
        for key, o in OATHS.items()
    ]


def summary(oaths: List[str]) -> Dict[str, Any]:
    """What the combat screen shows about the oaths in force."""
    if not oaths:
        return {"oaths": [], "reward_mult": 1.0, "reward_bonus_pct": 0}
    mult = reward_multiplier(oaths)
    return {
        "oaths": [
            {"id": k, "name": OATHS[k]["name"], "emoji": OATHS[k]["emoji"]} for k in oaths
        ],
        "reward_mult": round(mult, 3),
        "reward_bonus_pct": int(round((mult - 1.0) * 100)),
    }
